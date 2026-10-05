"""
system/screen_time_tracker.py
--------------------------------
Tracks how many seconds today the user has been actively at the
computer (i.e. not idle), persisting the running total to `MemoryDB`
so it survives restarts and app crashes (it's saved incrementally,
poll by poll, not only on clean shutdown).

"Active" is approximated as: idle time below a threshold, OR idle time
being undeterminable on this platform/session (we count time as active
rather than silently under-reporting on desktop environments where the
idle-time API isn't available, e.g. some Wayland sessions).
"""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QObject, QTimer

from database.memory_db import MemoryDB
from system import message_generator
from system.activity_monitor import ActivityMonitor
from utils.logger import get_logger

logger = get_logger(__name__)

_POLL_SECONDS = 30
_IDLE_CUTOFF_SECONDS = 120  # idle time at/above this doesn't count as "active"

# Milestones (seconds) -> category to draw a varied contextual message from.
# 30 min / 1 hour / 2 hours / 3 hours, per the spec; every full hour beyond
# that keeps announcing via the last (3h) entry's category so long sessions
# still get periodic nudges.
_MILESTONES: list[tuple[int, str]] = [
    (1800, "Screen Time"),
    (3600, "Break Reminder"),
    (7200, "Health"),
    (10800, "Exercise"),
]


def format_duration(total_seconds: int) -> str:
    """Turn a second count into a friendly 'Xh Ym' / 'Ym' string."""
    hours, remainder = divmod(max(0, total_seconds), 3600)
    minutes = remainder // 60
    if hours and minutes:
        return f"{hours}h {minutes}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


class ScreenTimeTracker(QObject):
    """Polls idle time and accumulates today's active screen time."""

    def __init__(
        self,
        memory_db: MemoryDB,
        on_milestone=None,  # Optional[Callable[[str, str], None]] - called with (message, category)
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._memory_db = memory_db
        self._on_milestone = on_milestone
        self._monitor = ActivityMonitor()

        today_seconds = self._today_seconds()
        # Don't re-fire milestones already passed earlier today (e.g. on restart).
        self._next_milestone_index = 0
        while (
            self._next_milestone_index < len(_MILESTONES)
            and today_seconds >= _MILESTONES[self._next_milestone_index][0]
        ):
            self._next_milestone_index += 1
        self._extra_hourly_announced = today_seconds // 3600

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)

    def start(self) -> None:
        self._timer.start(_POLL_SECONDS * 1000)
        logger.info("ScreenTimeTracker started (poll every %ds).", _POLL_SECONDS)

    def stop(self) -> None:
        self._timer.stop()

    # ------------------------------------------------------------------
    # Public queries
    # ------------------------------------------------------------------

    def today_seconds(self) -> int:
        return self._today_seconds()

    def today_formatted(self) -> str:
        return format_duration(self._today_seconds())

    def _today_seconds(self) -> int:
        return self._memory_db.get_screen_time_seconds(date.today().isoformat())

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        idle_seconds = self._monitor._idle_seconds()  # reuse existing best-effort idle detection

        is_active = idle_seconds is None or idle_seconds < _IDLE_CUTOFF_SECONDS
        if is_active:
            self._memory_db.add_screen_time_seconds(date.today().isoformat(), _POLL_SECONDS)

        if not self._on_milestone:
            return

        total_seconds = self._today_seconds()

        # The four named milestones (30m / 1h / 2h / 3h), each with its own category.
        while (
            self._next_milestone_index < len(_MILESTONES)
            and total_seconds >= _MILESTONES[self._next_milestone_index][0]
        ):
            _, category = _MILESTONES[self._next_milestone_index]
            message = message_generator.generate(category, duration=self.today_formatted())
            self._on_milestone(message, category)
            self._next_milestone_index += 1

        # Beyond 3 hours, keep nudging once per additional hour using the
        # same rotating "Health"/"Break Reminder" style messages.
        if self._next_milestone_index >= len(_MILESTONES):
            current_hour = total_seconds // 3600
            if current_hour > self._extra_hourly_announced:
                self._extra_hourly_announced = current_hour
                category = "Break Reminder" if current_hour % 2 == 0 else "Health"
                message = message_generator.generate(category, duration=self.today_formatted())
                self._on_milestone(message, category)
