"""Tests for window-position persistence (config/settings_manager.py)."""

from __future__ import annotations

from config.settings_manager import SettingsManager


def test_load_window_position_returns_none_when_never_saved(memory_db):
    mgr = SettingsManager(memory_db)
    assert mgr.load_window_position() is None


def test_save_and_load_window_position_round_trips(memory_db):
    mgr = SettingsManager(memory_db)
    mgr.save_window_position(555, 321)
    assert mgr.load_window_position() == (555, 321)


def test_window_position_survives_a_new_manager_instance(memory_db):
    # Simulates a real app restart: a brand-new SettingsManager against the
    # same on-disk database should still see the last saved position.
    SettingsManager(memory_db).save_window_position(42, 99)
    fresh_manager = SettingsManager(memory_db)
    assert fresh_manager.load_window_position() == (42, 99)
