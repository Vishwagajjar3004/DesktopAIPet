"""
voice/stt_engine.py
---------------------
Speech-to-text using the `SpeechRecognition` package. Prefers the
offline Sphinx backend when available (via `pocketsphinx`), and falls
back to Google's free web recognizer (requires internet) otherwise.

Runs listening in a background thread and reports the transcribed text
(or nothing, on failure/silence) via a callback, so it never blocks the
Qt event loop.
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

from config.settings import settings
from utils.logger import get_logger

import ctypes

logger = get_logger(__name__)


_c_error_handler = None


def _suppress_alsa_errors() -> None:
    """Mute noisy ALSA C-level debug output on Linux."""
    global _c_error_handler
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
        error_handler_type = ctypes.CFUNCTYPE(
            None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
        )

        def _py_handler(filename, line, function, err, fmt):
            pass

        _c_error_handler = error_handler_type(_py_handler)
        asound.snd_lib_error_set_handler(_c_error_handler)
    except Exception:
        pass


class STTEngine:
    """Thin wrapper around SpeechRecognition with graceful degradation."""

    def __init__(self) -> None:
        self._sr = None
        self._recognizer = None
        self._microphone = None
        self._available = self._try_init()

    def _try_init(self) -> bool:
        try:
            import speech_recognition as sr
        except ImportError:
            logger.warning(
                "SpeechRecognition not installed — STT disabled. "
                "Run: pip install SpeechRecognition pyaudio"
            )
            return False

        self._sr = sr
        self._recognizer = sr.Recognizer()

        try:
            _suppress_alsa_errors()
            self._microphone = sr.Microphone()
        except (OSError, AttributeError):
            logger.warning("No microphone detected — STT disabled.")
            return False

        return True

    @property
    def available(self) -> bool:
        return self._available

    def listen_once_async(self, on_result: Callable[[Optional[str]], None]) -> None:
        """
        Listen for a single utterance in a background thread and call
        `on_result(text)` with the transcript, or `on_result(None)` if
        nothing could be understood.
        """
        if not self._available or not settings.voice.stt_enabled:
            on_result(None)
            return
        thread = threading.Thread(target=self._listen_blocking, args=(on_result,), daemon=True)
        thread.start()

    def _listen_blocking(self, on_result: Callable[[Optional[str]], None]) -> None:
        sr = self._sr
        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                audio = self._recognizer.listen(source, timeout=5, phrase_time_limit=10)
        except Exception:  # noqa: BLE001
            logger.exception("STT listening failed.")
            on_result(None)
            return

        text = self._transcribe(audio)
        on_result(text)

    def _transcribe(self, audio) -> Optional[str]:
        sr = self._sr
        # Try offline Sphinx first (fully local), then fall back to the
        # free Google Web Speech API (needs internet, no key required).
        try:
            return self._recognizer.recognize_sphinx(audio, language=settings.voice.stt_language)
        except Exception:  # noqa: BLE001 - sphinx missing or failed
            pass

        try:
            return self._recognizer.recognize_google(audio, language=settings.voice.stt_language)
        except Exception:  # noqa: BLE001
            logger.info("Could not transcribe speech (offline and online recognizers both failed).")
            return None
