"""
plugins/example_reminder_plugin.py
--------------------------------------
A minimal example plugin demonstrating the plugin API: every 30 minutes
it has Asha gently remind the user to stretch. Copy this file's shape
to build new plugins — nothing outside `plugins/` needs to change.
"""

from __future__ import annotations

from PySide6.QtCore import QTimer

from animations.animation_controller import AnimationState
from plugins.plugin_base import AshaPlugin, PetAPI

_INTERVAL_MS = 30 * 60 * 1000  # 30 minutes


class StretchReminderPlugin(AshaPlugin):
    name = "stretch_reminder"
    description = "Reminds the user to stretch every 30 minutes."

    def __init__(self, api: PetAPI) -> None:
        super().__init__(api)
        self._timer: QTimer | None = None

    def on_load(self) -> None:
        self._timer = QTimer()
        self._timer.timeout.connect(self._remind)
        self._timer.start(_INTERVAL_MS)

    def _remind(self) -> None:
        self.api.set_animation_state(AnimationState.STRETCH)
        self.api.say("Stretch break! Roll your shoulders for a sec 🙆")

    def on_unload(self) -> None:
        if self._timer:
            self._timer.stop()
