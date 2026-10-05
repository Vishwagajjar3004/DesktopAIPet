"""
system/activity_monitor.py
-----------------------------
Polls the desktop environment for the signals the spec asks for:
mouse/keyboard activity & idle time, the active application, battery
status, network connectivity, time/date, and CPU/RAM usage.

Cross-platform notes:
    * CPU/RAM/battery/network: `psutil` (cross-platform).
    * Active window title: `pygetwindow` on Windows, best-effort via
      `wmctrl`/`xdotool` shell-out on Linux (X11). Wayland makes this
      generally unavailable at the OS level for security reasons; the
      monitor degrades to "unknown" rather than crashing there.
    * Global mouse/keyboard idle time: `psutil` doesn't provide this,
      so we track *our own* window's mouse focus as a proxy, but the
      most reliable cross-platform approach is OS-specific idle APIs
      (`GetLastInputInfo` on Windows, `org.freedesktop.ScreenSaver` or
      `xprintidle` on Linux). We shell out to those with graceful
      fallback to "unknown" idle time when unavailable.

Every method returns `None`/a sentinel instead of raising when a signal
can't be determined on the current platform, so `ReactionEngine` can
simply skip reactions it doesn't have data for.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

_IS_WINDOWS = platform.system() == "Windows"
_IS_LINUX = platform.system() == "Linux"


@dataclass
class SystemSnapshot:
    """One poll's worth of desktop-awareness data."""

    timestamp: datetime
    active_app: Optional[str]
    idle_seconds: Optional[float]
    battery_percent: Optional[int]
    battery_plugged: Optional[bool]
    network_connected: Optional[bool]
    cpu_percent: Optional[float]
    ram_percent: Optional[float]


class ActivityMonitor:
    """Gathers a `SystemSnapshot` on demand."""

    def snapshot(self) -> SystemSnapshot:
        return SystemSnapshot(
            timestamp=datetime.now(),
            active_app=self._active_app(),
            idle_seconds=self._idle_seconds(),
            battery_percent=self._battery_percent(),
            battery_plugged=self._battery_plugged(),
            network_connected=self._network_connected(),
            cpu_percent=self._cpu_percent(),
            ram_percent=self._ram_percent(),
        )

    # ------------------------------------------------------------------
    # Active application
    # ------------------------------------------------------------------

    def _active_app(self) -> Optional[str]:
        try:
            if _IS_WINDOWS:
                return self._active_app_windows()
            if _IS_LINUX:
                return self._active_app_linux()
        except Exception:  # noqa: BLE001
            logger.debug("Could not determine active app.", exc_info=True)
        return None

    @staticmethod
    def _active_app_windows() -> Optional[str]:
        try:
            import pygetwindow as gw
        except ImportError:
            logger.debug("pygetwindow not installed — active app detection disabled on Windows.")
            return None
        window = gw.getActiveWindow()
        return window.title if window else None

    @staticmethod
    def _active_app_linux() -> Optional[str]:
        # Best-effort under X11 via wmctrl; unavailable under Wayland.
        if shutil.which("xdotool") is None:
            return None
        try:
            window_id = subprocess.check_output(
                ["xdotool", "getactivewindow"], timeout=1, stderr=subprocess.DEVNULL
            ).decode().strip()
            name = subprocess.check_output(
                ["xdotool", "getwindowname", window_id], timeout=1, stderr=subprocess.DEVNULL
            ).decode().strip()
            return name or None
        except (subprocess.SubprocessError, OSError):
            return None

    # ------------------------------------------------------------------
    # Idle time
    # ------------------------------------------------------------------

    def _idle_seconds(self) -> Optional[float]:
        try:
            if _IS_LINUX:
                return self._idle_seconds_linux()
            if _IS_WINDOWS:
                return self._idle_seconds_windows()
        except Exception:  # noqa: BLE001
            logger.debug("Could not determine idle time.", exc_info=True)
        return None

    @staticmethod
    def _idle_seconds_linux() -> Optional[float]:
        if shutil.which("dbus-send"):
            try:
                out = subprocess.check_output(
                    [
                        "dbus-send",
                        "--print-reply",
                        "--dest=org.gnome.Mutter.IdleMonitor",
                        "/org/gnome/Mutter/IdleMonitor/Core",
                        "org.gnome.Mutter.IdleMonitor.GetIdletime",
                    ],
                    timeout=1,
                    stderr=subprocess.DEVNULL,
                ).decode()
                for line in out.splitlines():
                    if "uint64" in line:
                        return int(line.split()[-1]) / 1000.0
            except (subprocess.SubprocessError, OSError, ValueError):
                pass

        if shutil.which("xprintidle"):
            try:
                ms = subprocess.check_output(["xprintidle"], timeout=1, stderr=subprocess.DEVNULL).decode().strip()
                return int(ms) / 1000.0
            except (subprocess.SubprocessError, OSError, ValueError):
                pass

        return None

    @staticmethod
    def _idle_seconds_windows() -> Optional[float]:
        try:
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            info = LASTINPUTINFO()
            info.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):  # type: ignore[attr-defined]
                return None
            millis_idle = ctypes.windll.kernel32.GetTickCount() - info.dwTime  # type: ignore[attr-defined]
            return millis_idle / 1000.0
        except Exception:  # noqa: BLE001
            return None

    # ------------------------------------------------------------------
    # Battery / network / CPU / RAM (via psutil)
    # ------------------------------------------------------------------

    def _battery_percent(self) -> Optional[int]:
        battery = self._psutil_battery()
        return int(battery.percent) if battery else None

    def _battery_plugged(self) -> Optional[bool]:
        battery = self._psutil_battery()
        return bool(battery.power_plugged) if battery else None

    @staticmethod
    def _psutil_battery():
        try:
            import psutil

            return psutil.sensors_battery()
        except (ImportError, Exception):  # noqa: BLE001
            return None

    @staticmethod
    def _network_connected() -> Optional[bool]:
        try:
            import socket

            socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
            return True
        except OSError:
            return False

    @staticmethod
    def _cpu_percent() -> Optional[float]:
        try:
            import psutil

            return psutil.cpu_percent(interval=None)
        except ImportError:
            return None

    @staticmethod
    def _ram_percent() -> Optional[float]:
        try:
            import psutil

            return psutil.virtual_memory().percent
        except ImportError:
            return None
