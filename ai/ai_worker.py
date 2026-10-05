"""
ai/ai_worker.py
------------------
Runs `AIManager.send_message` on a background QThread so a slow network
call (OpenAI) or local model (Ollama) never freezes the Qt UI thread.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from ai.ai_manager import AIManager
from utils.logger import get_logger

logger = get_logger(__name__)


class AIWorker(QThread):
    """One-shot worker thread: sends a single message, emits the reply."""

    reply_ready = Signal(str)
    failed = Signal(str)

    def __init__(self, ai_manager: AIManager, user_text: str, parent=None) -> None:
        super().__init__(parent)
        self._ai_manager = ai_manager
        self._user_text = user_text

    def run(self) -> None:  # noqa: D102 (QThread override)
        try:
            reply = self._ai_manager.send_message(self._user_text)
            self.reply_ready.emit(reply)
        except Exception as exc:  # noqa: BLE001 - last line of defense
            logger.exception("AIWorker failed unexpectedly")
            self.failed.emit(str(exc))
