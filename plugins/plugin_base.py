"""
plugins/plugin_base.py
-------------------------
Base class every plugin must subclass, plus the small `PetAPI` facade
handed to plugins so they can interact with the pet (say things,
change animation state) without importing UI internals directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable

from animations.animation_controller import AnimationState


@dataclass
class PetAPI:
    """
    The limited, stable surface plugins are allowed to touch. Keeping
    this small means Asha's internals can change without breaking
    third-party plugins.
    """

    say: Callable[[str], None]
    set_animation_state: Callable[[AnimationState], None]


class AshaPlugin(ABC):
    """
    Subclass this and implement `name`, `description`, and `on_load` to
    build a plugin. Drop the .py file into `plugins/` and it will be
    auto-discovered by `PluginManager` at startup.
    """

    #: Short unique identifier, e.g. "reminder_popup"
    name: str = "unnamed_plugin"

    #: One-line human-readable description (shown in a future plugin
    #: manager UI).
    description: str = ""

    def __init__(self, api: PetAPI) -> None:
        self.api = api

    @abstractmethod
    def on_load(self) -> None:
        """Called once when the plugin is activated. Wire up timers,
        register menu items (future extension point), etc. here."""
        raise NotImplementedError

    def on_unload(self) -> None:
        """Optional cleanup hook, called on app shutdown or plugin disable."""
        return None
