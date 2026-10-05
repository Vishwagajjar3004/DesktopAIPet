"""
system/startup_manager.py
----------------------------
Registers/unregisters Asha to launch automatically when the user logs
in.

    * Windows: writes/removes a value under
      HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
    * Linux: writes/removes a `.desktop` file under
      ~/.config/autostart/ (freedesktop.org autostart spec, supported
      by GNOME, KDE, XFCE, and most other desktop environments)

Both operations are best-effort and log + return False on failure
rather than raising, since this is a "nice to have" preference, not
core functionality.
"""

from __future__ import annotations

import platform
import sys
from pathlib import Path

from config.settings import APP_NAME, PROJECT_ROOT
from utils.logger import get_logger

logger = get_logger(__name__)

_IS_WINDOWS = platform.system() == "Windows"


def _linux_autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / f"{APP_NAME.lower()}.desktop"


def enable_startup() -> bool:
    try:
        if _IS_WINDOWS:
            return _enable_startup_windows()
        return _enable_startup_linux()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to enable startup-with-OS.")
        return False


def disable_startup() -> bool:
    try:
        if _IS_WINDOWS:
            return _disable_startup_windows()
        return _disable_startup_linux()
    except Exception:  # noqa: BLE001
        logger.exception("Failed to disable startup-with-OS.")
        return False


def is_startup_enabled() -> bool:
    try:
        if _IS_WINDOWS:
            return _is_startup_enabled_windows()
        return _linux_autostart_path().exists()
    except Exception:  # noqa: BLE001
        return False


# ---------------------------------------------------------------------------
# Windows (registry Run key)
# ---------------------------------------------------------------------------

def _enable_startup_windows() -> bool:
    import winreg  # type: ignore[import-not-found]

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    command = f'"{sys.executable}" "{PROJECT_ROOT / "main.py"}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
    logger.info("Startup-with-Windows enabled.")
    return True


def _disable_startup_windows() -> bool:
    import winreg  # type: ignore[import-not-found]

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
        try:
            winreg.DeleteValue(key, APP_NAME)
        except FileNotFoundError:
            pass
    logger.info("Startup-with-Windows disabled.")
    return True


def _is_startup_enabled_windows() -> bool:
    import winreg  # type: ignore[import-not-found]

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False


# ---------------------------------------------------------------------------
# Linux (.desktop autostart file)
# ---------------------------------------------------------------------------

def _enable_startup_linux() -> bool:
    autostart_path = _linux_autostart_path()
    autostart_path.parent.mkdir(parents=True, exist_ok=True)
    content = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        f'Exec="{sys.executable}" "{PROJECT_ROOT / "main.py"}"\n'
        "X-GNOME-Autostart-enabled=true\n"
    )
    autostart_path.write_text(content, encoding="utf-8")
    logger.info("Startup-with-Linux-session enabled (%s).", autostart_path)
    return True


def _disable_startup_linux() -> bool:
    autostart_path = _linux_autostart_path()
    if autostart_path.exists():
        autostart_path.unlink()
    logger.info("Startup-with-Linux-session disabled.")
    return True
