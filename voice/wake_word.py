"""
voice/wake_word.py
---------------------
Lightweight wake-word listener: continuously listens in a background
thread and calls back when the configured phrase (default "hey asha")
is heard, reusing `STTEngine` rather than pulling in a separate
heavyweight wake-word engine (Porcupine etc. can be swapped in later
as a plugin if lower latency is needed).

This is a simple polling loop, not millisecond-accurate wake-word
detection — appropriate for a friendly desktop companion, not a
security product.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Optional

from config.settings import settings
from utils.logger import get_logger
from voice.stt_engine import STTEngine

logger = get_logger(__name__)


class WakeWordListener:
    """Repeatedly listens for short phrases and checks for the wake word."""

    def __init__(self, stt_engine: STTEngine, on_wake: Callable[[], None]) -> None:
        self._stt = stt_engine
        self._on_wake = on_wake
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @property
    def available(self) -> bool:
        return self._stt.available

    def start(self) -> None:
        if not self.available:
            logger.warning("Wake-word listener not started — STT unavailable.")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("Wake-word listener started (phrase=%r).", settings.voice.wake_word)

    def stop(self) -> None:
        self._running = False
        logger.info("Wake-word listener stopped.")

    def _loop(self) -> None:
        while self._running and settings.voice.wake_word_enabled:
            heard: list[Optional[str]] = [None]
            done = threading.Event()

            def _capture(text: Optional[str]) -> None:
                heard[0] = text
                done.set()

            self._stt.listen_once_async(_capture)
            done.wait(timeout=12)

            if heard[0] and settings.voice.wake_word.lower() in heard[0].lower():
                logger.info("Wake word detected.")
                self._on_wake()

            time.sleep(0.2)  # small breather between listen cycles
