"""Tests for plugins/plugin_manager.py — verifies real discovery of the
shipped example plugin via importlib, not a mock."""

from __future__ import annotations

from animations.animation_controller import AnimationState
from plugins.plugin_base import PetAPI
from plugins.plugin_manager import PluginManager


def test_discovers_and_loads_example_plugin():
    said = []
    states = []
    api = PetAPI(say=said.append, set_animation_state=states.append)

    manager = PluginManager(api)
    loaded = manager.discover_and_load()

    assert "stretch_reminder" in loaded
    manager.unload_all()


def test_plugin_can_trigger_pet_api(monkeypatch):
    said = []
    states = []
    api = PetAPI(say=said.append, set_animation_state=states.append)

    from plugins.example_reminder_plugin import StretchReminderPlugin

    plugin = StretchReminderPlugin(api)
    plugin.on_load()
    plugin._remind()  # simulate the timer firing directly, no need to wait 30 min

    assert states[-1] == AnimationState.STRETCH
    assert "stretch" in said[-1].lower() or "🙆" in said[-1]
    plugin.on_unload()
