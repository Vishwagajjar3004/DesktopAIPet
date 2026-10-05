"""
voice/tts_engine.py
---------------------
Offline text-to-speech using `pyttsx3` (wraps SAPI5 on Windows, espeak
on Linux) — no internet or API key required.

Runs speech synthesis in a background thread so it never blocks the Qt
event loop / UI.
"""

from __future__ import annotations

import threading
from typing import Optional

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class TTSEngine:
    """Thin, thread-safe wrapper around pyttsx3."""

    def __init__(self) -> None:
        self._engine = None
        self._lock = threading.Lock()
        self._available = self._try_init()

    def _try_init(self) -> bool:
        try:
            import pyttsx3
        except ImportError:
            logger.warning("pyttsx3 not installed — TTS disabled. Run: pip install pyttsx3")
            return False

        try:
            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", settings.voice.tts_rate)
            self._engine.setProperty("volume", settings.voice.tts_volume)
            if settings.voice.tts_voice_id:
                self._engine.setProperty("voice", settings.voice.tts_voice_id)
            else:
                self._auto_select_female_voice()
            return True
        except Exception:  # noqa: BLE001 - platform TTS backends fail in many ways
            logger.exception("Failed to initialize pyttsx3 TTS engine — TTS disabled.")
            return False

    def _auto_select_female_voice(self) -> None:
        """
        Asha is a girl character, so by default we pick a female-sounding
        voice rather than whatever the OS's TTS default happens to be
        (often a male voice). Picked via the driver's own gender metadata
        when available, then a name-based heuristic covering the common
        female voices shipped with Windows SAPI5 (Zira, Hazel, Eva...),
        macOS/other engines (Samantha, Victoria, Karen, Moira...), and
        espeak-ng's female variant suffixes (+f3, +f4...).

        If nothing matches, we fall back to the engine's own default
        voice rather than guessing wrong — this never breaks TTS, it
        only makes a best-effort pick when it can.
        """
        female_keywords = [
            "female", "zira", "hazel", "eva", "samantha", "victoria", "susan",
            "karen", "moira", "tessa", "fiona", "salli", "joanna", "kendra",
            "kimberly", "ivy", "raveena", "aditi", "f1", "f2", "f3", "f4", "f5",
        ]
        try:
            voices = self._engine.getProperty("voices")
        except Exception:  # noqa: BLE001
            return

        for voice in voices:
            gender = getattr(voice, "gender", None)
            if gender and "female" in str(gender).lower():
                self._engine.setProperty("voice", voice.id)
                logger.info("Auto-selected female voice (by gender metadata): %s", voice.name)
                return

        for voice in voices:
            haystack = f"{(voice.name or '').lower()} {(voice.id or '').lower()}"
            if any(keyword in haystack for keyword in female_keywords):
                self._engine.setProperty("voice", voice.id)
                logger.info("Auto-selected female voice (by name match): %s", voice.name)
                return

        logger.info("No clearly female voice found on this system — using the engine default.")

    @property
    def available(self) -> bool:
        return self._available

    def list_voices(self) -> list[tuple[str, str]]:
        """Return [(voice_id, human_readable_name), ...] for the Settings UI."""
        if not self._available:
            return []
        with self._lock:
            return [(v.id, v.name) for v in self._engine.getProperty("voices")]

    def speak(self, text: str) -> None:
        """Speak `text` asynchronously (returns immediately)."""
        if not self._available or settings.muted or not settings.voice.tts_enabled:
            return
        thread = threading.Thread(target=self._speak_blocking, args=(text,), daemon=True)
        thread.start()

    def _speak_blocking(self, text: str) -> None:
        with self._lock:
            try:
                self._engine.say(text)
                self._engine.runAndWait()
            except Exception:  # noqa: BLE001
                logger.exception("TTS playback failed.")

    def stop(self) -> None:
        if self._available:
            try:
                self._engine.stop()
            except Exception:  # noqa: BLE001
                pass
