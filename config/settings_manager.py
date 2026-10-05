"""
config/settings_manager.py
---------------------------
Loads/saves the mutable parts of `Settings` (theme, volume, AI provider,
outfit, etc.) to/from the SQLite database, so preferences survive
restarts. Falls back silently to in-memory defaults if the database
isn't available yet (e.g. first run before `database.memory_db` has
created its tables).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from config.settings import Settings, settings
from utils.logger import get_logger

logger = get_logger(__name__)

# Flat keys we persist as simple key/value pairs in the `preferences` table.
_PERSISTED_KEYS = [
    "theme",
    "language",
    "volume",
    "muted",
    "outfit",
    "start_with_os",
]


class SettingsManager:
    """Bridges the in-memory `Settings` dataclass and SQLite persistence."""

    def __init__(self, db: "MemoryDB | None" = None) -> None:  # noqa: F821 (forward ref)
        self._db = db

    def load(self) -> Settings:
        if self._db is None:
            return settings
        for key in _PERSISTED_KEYS:
            value = self._db.get_preference(key)
            if value is None:
                continue
            self._apply_value(key, value)
        logger.info("Settings loaded from database.")
        return settings

    def save(self) -> None:
        if self._db is None:
            return
        for key in _PERSISTED_KEYS:
            self._db.set_preference(key, str(getattr(settings, key)))
        logger.info("Settings saved to database.")

    def save_window_position(self, x: int, y: int) -> None:
        """Persist the pet's on-screen position so it reappears in the same
        spot after a restart (Feature 1 in the spec)."""
        if self._db is None:
            return
        self._db.set_preference("window_x", str(x))
        self._db.set_preference("window_y", str(y))

    def load_window_position(self) -> tuple[int, int] | None:
        """Return the last-saved (x, y) position, or None if never saved."""
        if self._db is None:
            return None
        x = self._db.get_preference("window_x")
        y = self._db.get_preference("window_y")
        if x is None or y is None:
            return None
        try:
            return int(x), int(y)
        except ValueError:
            logger.warning("Could not parse persisted window position %r, %r", x, y)
            return None

    @staticmethod
    def _apply_value(key: str, raw_value: str) -> None:
        current = getattr(settings, key)
        try:
            if isinstance(current, bool):
                setattr(settings, key, raw_value.lower() in ("1", "true", "yes"))
            elif isinstance(current, float):
                setattr(settings, key, float(raw_value))
            elif isinstance(current, int):
                setattr(settings, key, int(raw_value))
            else:
                setattr(settings, key, raw_value)
        except (ValueError, TypeError):
            logger.warning("Could not apply persisted setting %s=%r", key, raw_value)

    def as_dict(self) -> dict[str, Any]:
        """Full snapshot of current settings (used by the Settings dialog)."""
        return asdict(settings)
