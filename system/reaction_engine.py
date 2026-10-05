"""
system/reaction_engine.py
----------------------------
Turns `ActivityMonitor` snapshots into the "smart reactions" described
in the spec (VS Code opened, idle too long, low battery, continuous
typing, welcome back, etc.), each said through a callback (normally
`PetWindow.say`).

A per-reaction-type cooldown (`AwarenessSettings.reaction_cooldown_seconds`)
stops Asha from spamming the same comment every poll cycle.
"""

from __future__ import annotations

import time
from typing import Callable, Optional

from PySide6.QtCore import QObject, QTimer

from config.settings import settings
from database.memory_db import MemoryDB
from system import message_generator
from system.activity_monitor import ActivityMonitor, SystemSnapshot
from utils.logger import get_logger

logger = get_logger(__name__)

# Keyword -> (comment, category), checked against the active window title
# (case-insensitive).
_APP_REACTIONS: list[tuple[str, str, str]] = [
    ("code", "Back to coding? 👩‍💻", "Focus"),
    ("visual studio", "Back to coding? 👩‍💻", "Focus"),
    ("chrome", "Research... or YouTube? 👀", "General"),
    ("firefox", "Research... or YouTube? 👀", "General"),
    ("edge", "Research... or YouTube? 👀", "General"),
    ("spotify", "Ooh, what are we listening to?", "General"),
    ("terminal", "Living in the terminal today, huh?", "Productivity"),
]


class ReactionEngine(QObject):
    """Polls `ActivityMonitor` on a timer and fires contextual one-liners."""

    def __init__(
        self,
        say_callback: Callable[[str, str], None],
        memory_db: Optional[MemoryDB] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._say = say_callback
        self._memory_db = memory_db
        self._monitor = ActivityMonitor()

        self._last_active_app: Optional[str] = None
        self._was_idle = False
        self._idle_since: Optional[float] = None
        self._typing_streak_start: Optional[float] = None
        self._last_reaction_time: dict[str, float] = {}

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        if not settings.awareness.enabled:
            logger.info("Desktop awareness disabled in settings; not starting ReactionEngine.")
            return
        self._timer.start(settings.awareness.poll_interval_ms)
        logger.info("ReactionEngine started (poll interval=%dms).", settings.awareness.poll_interval_ms)

    def stop(self) -> None:
        self._timer.stop()

    # ------------------------------------------------------------------
    # Core poll loop
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        snapshot = self._monitor.snapshot()
        self._check_active_app(snapshot)
        self._check_idle(snapshot)
        self._check_battery(snapshot)

    # ------------------------------------------------------------------
    # Individual reaction checks
    # ------------------------------------------------------------------

    def _check_active_app(self, snapshot: SystemSnapshot) -> None:
        app = snapshot.active_app
        if not app or app == self._last_active_app:
            return

        self._last_active_app = app
        if self._memory_db:
            self._memory_db.record_app_seen(app)

        app_lower = app.lower()
        for keyword, message, category in _APP_REACTIONS:
            if keyword in app_lower:
                self._fire(f"app:{keyword}", message, category)
                return

    def _check_idle(self, snapshot: SystemSnapshot) -> None:
        idle = snapshot.idle_seconds
        if idle is None:
            return

        is_idle_now = idle >= settings.awareness.idle_threshold_seconds

        if is_idle_now and not self._was_idle:
            self._idle_since = time.monotonic()
            self._fire("idle_start", "Coffee break? ☕ I'll be here.", "Break Reminder")

        elif not is_idle_now and self._was_idle:
            # User just came back — decide between a short "welcome back"
            # and nothing, based on how long they were away.
            away_for = idle  # idle at the moment just before returning is a decent proxy
            if away_for >= settings.awareness.away_threshold_seconds:
                self._fire("welcome_back", "Welcome back! Missed you. 💜", "General")
            self._idle_since = None
            self._typing_streak_start = None

        elif not is_idle_now:
            # Active: track a "continuous typing" streak proxy.
            if self._typing_streak_start is None:
                self._typing_streak_start = time.monotonic()
            elapsed = time.monotonic() - self._typing_streak_start
            if elapsed >= settings.awareness.typing_streak_seconds:
                message = message_generator.generate("Compliment")
                self._fire("typing_streak", message, "Compliment")
                self._typing_streak_start = time.monotonic()  # reset so it can fire again later
        else:
            # Still idle, nothing new to say.
            pass

        self._was_idle = is_idle_now

    def _check_battery(self, snapshot: SystemSnapshot) -> None:
        if snapshot.battery_percent is None or snapshot.battery_plugged is None:
            return
        low = snapshot.battery_percent <= settings.awareness.low_battery_threshold_percent
        if low and not snapshot.battery_plugged:
            self._fire(
                "low_battery",
                f"Battery's at {snapshot.battery_percent}%! Plug in your charger. 🔌",
                "General",
            )

    # ------------------------------------------------------------------
    # Cooldown-aware firing
    # ------------------------------------------------------------------

    def _fire(self, reaction_key: str, message: str, category: str = "General") -> None:
        now = time.monotonic()
        last_fired = self._last_reaction_time.get(reaction_key, 0.0)
        if now - last_fired < settings.awareness.reaction_cooldown_seconds:
            return
        self._last_reaction_time[reaction_key] = now
        logger.debug("Reaction fired: %s -> %r (%s)", reaction_key, message, category)
        self._say(message, category)
