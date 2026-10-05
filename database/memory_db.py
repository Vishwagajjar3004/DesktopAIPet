"""
database/memory_db.py
----------------------
SQLite persistence layer for Asha's long-term memory.

Tables:
    preferences         key/value store for simple settings
    conversation_history full chat log (role, content, timestamp)
    favorite_apps        apps the user is frequently seen using
    reminders             user-set reminders
    user_profile          single-row table: name, relationship_level, etc.

This is intentionally a thin wrapper around stdlib `sqlite3` rather than
an ORM, to keep the dependency footprint at zero for something this
small -- easy to swap for SQLAlchemy later if the schema grows a lot.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from config.settings import DATABASE_FILE
from utils.logger import get_logger

logger = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    role       TEXT NOT NULL,             -- 'user' or 'assistant'
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS favorite_apps (
    app_name   TEXT PRIMARY KEY,
    open_count INTEGER NOT NULL DEFAULT 1,
    last_seen  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reminders (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    text       TEXT NOT NULL,
    remind_at  TEXT,                       -- ISO datetime, nullable (no specific time)
    is_done    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS user_profile (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    user_name          TEXT,
    relationship_level INTEGER NOT NULL DEFAULT 0,
    updated_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS screen_time (
    date          TEXT PRIMARY KEY,      -- 'YYYY-MM-DD'
    active_seconds INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    message     TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'General',
    timestamp   TEXT NOT NULL,           -- ISO datetime, UTC
    screen_time INTEGER,                 -- seconds of active screen time when said, nullable
    mood        TEXT                     -- pet's mood/animation state when said, nullable
);

CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_category ON messages (category);
"""

#: Canonical category list shown in the History Panel filter dropdown.
MESSAGE_CATEGORIES: list[str] = [
    "Health",
    "Break Reminder",
    "Screen Time",
    "Focus",
    "Compliment",
    "Motivation",
    "Productivity",
    "Water Reminder",
    "Exercise",
    "General",
]


@dataclass
class MessageLogEntry:
    id: int
    message: str
    category: str
    timestamp: str  # ISO datetime, UTC
    screen_time: Optional[int]
    mood: Optional[str]


@dataclass
class ChatMessage:
    role: str
    content: str
    created_at: str


class MemoryDB:
    """Owns the SQLite connection and exposes typed helper methods."""

    def __init__(self, db_path: Path = DATABASE_FILE) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        logger.info("MemoryDB ready at %s", self._db_path)

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO user_profile (id, user_name, relationship_level, updated_at) "
                "VALUES (1, NULL, 0, ?)",
                (datetime.now(timezone.utc).isoformat(),),
            )

    # ------------------------------------------------------------------
    # Preferences (key/value)
    # ------------------------------------------------------------------

    def get_preference(self, key: str) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM preferences WHERE key = ?", (key,)).fetchone()
            return row["value"] if row else None

    def set_preference(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO preferences (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    # ------------------------------------------------------------------
    # Conversation history
    # ------------------------------------------------------------------

    def add_message(self, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO conversation_history (role, content, created_at) VALUES (?, ?, ?)",
                (role, content, datetime.now(timezone.utc).isoformat()),
            )

    def get_recent_messages(self, limit: int = 20) -> list[ChatMessage]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT role, content, created_at FROM conversation_history "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        messages = [ChatMessage(r["role"], r["content"], r["created_at"]) for r in rows]
        messages.reverse()  # chronological order
        return messages

    def clear_conversation_history(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM conversation_history")

    # ------------------------------------------------------------------
    # Favorite apps
    # ------------------------------------------------------------------

    def record_app_seen(self, app_name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO favorite_apps (app_name, open_count, last_seen) VALUES (?, 1, ?) "
                "ON CONFLICT(app_name) DO UPDATE SET "
                "open_count = open_count + 1, last_seen = excluded.last_seen",
                (app_name, datetime.now(timezone.utc).isoformat()),
            )

    def top_favorite_apps(self, limit: int = 5) -> list[tuple[str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT app_name, open_count FROM favorite_apps "
                "ORDER BY open_count DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [(r["app_name"], r["open_count"]) for r in rows]

    # ------------------------------------------------------------------
    # Reminders
    # ------------------------------------------------------------------

    def add_reminder(self, text: str, remind_at: Optional[str] = None) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO reminders (text, remind_at, is_done, created_at) VALUES (?, ?, 0, ?)",
                (text, remind_at, datetime.now(timezone.utc).isoformat()),
            )
            return cursor.lastrowid

    def pending_reminders(self) -> list[sqlite3.Row]:
        with self._connect() as conn:
            return conn.execute(
                "SELECT id, text, remind_at FROM reminders WHERE is_done = 0 ORDER BY id"
            ).fetchall()

    def mark_reminder_done(self, reminder_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE reminders SET is_done = 1 WHERE id = ?", (reminder_id,))

    # ------------------------------------------------------------------
    # User profile / relationship level
    # ------------------------------------------------------------------

    def get_user_name(self) -> Optional[str]:
        with self._connect() as conn:
            row = conn.execute("SELECT user_name FROM user_profile WHERE id = 1").fetchone()
            return row["user_name"] if row else None

    def set_user_name(self, name: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_profile SET user_name = ?, updated_at = ? WHERE id = 1",
                (name, datetime.now(timezone.utc).isoformat()),
            )

    def get_relationship_level(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT relationship_level FROM user_profile WHERE id = 1").fetchone()
            return row["relationship_level"] if row else 0

    def increment_relationship_level(self, amount: int = 1) -> int:
        with self._connect() as conn:
            conn.execute(
                "UPDATE user_profile SET relationship_level = relationship_level + ?, updated_at = ? WHERE id = 1",
                (amount, datetime.now(timezone.utc).isoformat()),
            )
            row = conn.execute("SELECT relationship_level FROM user_profile WHERE id = 1").fetchone()
            return row["relationship_level"]

    # ------------------------------------------------------------------
    # Screen time
    # ------------------------------------------------------------------

    def add_screen_time_seconds(self, date_str: str, seconds: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO screen_time (date, active_seconds) VALUES (?, ?) "
                "ON CONFLICT(date) DO UPDATE SET active_seconds = active_seconds + excluded.active_seconds",
                (date_str, seconds),
            )

    def get_screen_time_seconds(self, date_str: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT active_seconds FROM screen_time WHERE date = ?", (date_str,)
            ).fetchone()
            return row["active_seconds"] if row else 0

    # ------------------------------------------------------------------
    # Message log (everything Asha says, for the History Panel)
    # ------------------------------------------------------------------

    def add_message_log(
        self,
        message: str,
        category: str = "General",
        screen_time: Optional[int] = None,
        mood: Optional[str] = None,
    ) -> int:
        """Record a message Asha spoke. Nothing is ever deleted automatically."""
        if category not in MESSAGE_CATEGORIES:
            category = "General"
        with self._connect() as conn:
            cursor = conn.execute(
                "INSERT INTO messages (message, category, timestamp, screen_time, mood) "
                "VALUES (?, ?, ?, ?, ?)",
                (message, category, datetime.now(timezone.utc).isoformat(), screen_time, mood),
            )
            return cursor.lastrowid

    def get_message_logs(
        self,
        category: Optional[str] = None,
        search: Optional[str] = None,
        since_iso: Optional[str] = None,
        until_iso: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[MessageLogEntry]:
        """Return message logs, newest first, with optional filters.

        `since_iso`/`until_iso` bound the ISO `timestamp` column (inclusive
        lower bound, exclusive upper bound) -- used for the Today/Yesterday/
        Last 7 Days/Last 30 Days timeline filters in the History Panel.
        """
        clauses: list[str] = []
        params: list[object] = []

        if category and category != "All":
            clauses.append("category = ?")
            params.append(category)
        if search:
            clauses.append("message LIKE ?")
            params.append(f"%{search}%")
        if since_iso:
            clauses.append("timestamp >= ?")
            params.append(since_iso)
        if until_iso:
            clauses.append("timestamp < ?")
            params.append(until_iso)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = f"LIMIT {int(limit)}" if limit else ""

        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT id, message, category, timestamp, screen_time, mood "
                f"FROM messages {where} ORDER BY timestamp DESC {limit_sql}",
                params,
            ).fetchall()

        return [
            MessageLogEntry(
                id=r["id"],
                message=r["message"],
                category=r["category"],
                timestamp=r["timestamp"],
                screen_time=r["screen_time"],
                mood=r["mood"],
            )
            for r in rows
        ]

    def clear_message_logs(self) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM messages")
