"""Tests for config/settings.py and config/settings_manager.py."""

from __future__ import annotations

from config.settings import Settings
from config.settings_manager import SettingsManager


def test_settings_defaults_are_sane():
    s = Settings()
    assert 0.0 <= s.window.opacity <= 1.0
    assert 0.0 <= s.volume <= 1.0
    assert s.animation.fps > 0


def test_settings_manager_persists_and_reloads(memory_db):
    from config.settings import settings

    manager = SettingsManager(memory_db)
    settings.theme = "light"
    settings.volume = 0.42
    manager.save()

    # Simulate a fresh process by mutating in-memory settings away from
    # what was saved, then reloading from the DB.
    settings.theme = "dark"
    settings.volume = 0.1
    manager.load()

    assert settings.theme == "light"
    assert abs(settings.volume - 0.42) < 1e-9
