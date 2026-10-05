"""Tests for system/screen_time_tracker.py."""

from __future__ import annotations

from datetime import date

from system.screen_time_tracker import ScreenTimeTracker, format_duration


def test_format_duration_variants():
    assert format_duration(0) == "0m"
    assert format_duration(59) == "0m"
    assert format_duration(60) == "1m"
    assert format_duration(3600) == "1h"
    assert format_duration(3900) == "1h 5m"


def test_tracker_reads_zero_seconds_initially(qapp, memory_db):
    tracker = ScreenTimeTracker(memory_db=memory_db)
    assert tracker.today_seconds() == 0
    assert tracker.today_formatted() == "0m"


def test_tracker_reflects_db_writes(qapp, memory_db):
    memory_db.add_screen_time_seconds(date.today().isoformat(), 125)
    tracker = ScreenTimeTracker(memory_db=memory_db)
    assert tracker.today_seconds() == 125
    assert tracker.today_formatted() == "2m"
