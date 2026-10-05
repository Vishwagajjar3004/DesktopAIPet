"""
main.py
-------
Entry point for the Desktop AI Pet (Asha) application.

Responsibilities:
    1. Create the QApplication (configured so closing the last window
       does NOT quit the app — minimizing to tray must keep it alive).
    2. Ensure required directories exist.
    3. Create the PetWindow (frameless, transparent, draggable, on top,
       with AI chat, voice, desktop awareness, plugins, and settings
       already wired in).
    4. Create the SystemTray icon and wire it to show/hide/exit.
    5. Run the Qt event loop.

Run with:
    python main.py
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from config.settings import APP_NAME, ORG_NAME, ensure_directories
from ui.pet_window import PetWindow
from ui.system_tray import SystemTray
from utils.logger import get_logger

logger = get_logger(__name__)


def main() -> int:
    ensure_directories()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)

    # Keep running even when the pet window is hidden (e.g. minimized to
    # tray) — only an explicit Exit (tray or context menu) should quit.
    app.setQuitOnLastWindowClosed(False)

    pet_window = PetWindow()
    pet_window.show()

    tray = SystemTray(
        parent=pet_window,
        on_toggle_visibility=pet_window.toggle_visibility,
        on_exit=app.quit,
        on_disable_click_through=lambda: pet_window.set_click_through(False),
    )
    tray.show()

    # Save position/settings no matter which path triggers quit (context
    # menu Exit, tray Exit, or the OS closing the app) so a restart always
    # restores the last known window position.
    app.aboutToQuit.connect(pet_window.save_state)

    pet_window.say("Hi! I'm vishwa 💜 Right-click me to see what I can do.")

    logger.info("Asha is running.")
    exit_code = app.exec()
    logger.info("Asha exited with code %d", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
