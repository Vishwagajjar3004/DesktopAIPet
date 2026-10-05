"""
ui/system_tray.py
------------------
System tray integration: lets the user minimize Asha to the tray, and
provides the tray-icon context menu (a subset of the full right-click
pet menu -- Chat/Sleep/Dance/etc. are added to the pet's own context
menu directly in ``pet_window.py``; the tray menu focuses on
show/hide/exit which are useful even when the pet window is hidden).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMenu, QStyle, QSystemTrayIcon, QWidget

from config.settings import APP_NAME, ICONS_DIR
from utils.logger import get_logger

logger = get_logger(__name__)


class SystemTray(QSystemTrayIcon):
    """Tray icon with Show/Hide and Exit actions for the pet window."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        on_toggle_visibility: Optional[Callable[[], None]] = None,
        on_exit: Optional[Callable[[], None]] = None,
        on_disable_click_through: Optional[Callable[[], None]] = None,
    ) -> None:
        icon = self._load_icon()
        super().__init__(icon, parent)

        self.setToolTip(APP_NAME)
        self._on_toggle_visibility = on_toggle_visibility
        self._on_exit = on_exit
        self._on_disable_click_through = on_disable_click_through

        self._menu = QMenu(parent)

        self._toggle_action = self._menu.addAction("Show / Hide Asha")
        self._toggle_action.triggered.connect(self._handle_toggle)

        if on_disable_click_through is not None:
            # Recovery path: if click-through mode ever gets left ON, the
            # pet ignores every mouse click (including right-click), so the
            # normal context menu becomes unreachable. The tray icon still
            # works, so this is the way back in.
            recovery_action = self._menu.addAction("🖱️ Disable Click-through")
            recovery_action.triggered.connect(self._handle_disable_click_through)

        self._menu.addSeparator()

        self._exit_action = self._menu.addAction("Exit")
        self._exit_action.triggered.connect(self._handle_exit)

        self.setContextMenu(self._menu)
        self.activated.connect(self._handle_activation)

        logger.info("System tray icon initialized.")

    @staticmethod
    def _load_icon() -> QIcon:
        for filename in ("tray_icon.png", "tray_icon.jpeg", "tray_icon.jpg", "tray_icon.ico"):
            icon_path = ICONS_DIR / filename
            if icon_path.exists():
                return QIcon(str(icon_path))
        # Fall back to a built-in Qt icon so the tray still works before
        # a real branded icon asset is supplied.
        logger.warning("No tray icon found in %s; using fallback icon.", ICONS_DIR)
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    def _handle_activation(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left-click (Trigger) toggles visibility, same as the menu item.
        if reason == QSystemTrayIcon.Trigger:
            self._handle_toggle()

    def _handle_toggle(self) -> None:
        if self._on_toggle_visibility:
            self._on_toggle_visibility()

    def _handle_disable_click_through(self) -> None:
        if self._on_disable_click_through:
            self._on_disable_click_through()

    def _handle_exit(self) -> None:
        logger.info("Exit requested from system tray.")
        if self._on_exit:
            self._on_exit()
