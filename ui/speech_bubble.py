"""
ui/speech_bubble.py
--------------------
A small frameless, transparent popup that renders a comic-style speech
bubble above the pet, with a typewriter ("typing") text animation and
automatic hide-after-timeout behaviour.

Phase 1 keeps this plain-text only; Markdown rendering (mentioned as
optional in the spec) can be layered on top of ``QLabel`` rich text in a
later phase without changing the public API of ``SpeechBubble``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from config.settings import settings
from utils.logger import get_logger

logger = get_logger(__name__)


class SpeechBubble(QWidget):
    """A borderless popup bubble that types out a message, then auto-hides."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self._full_text: str = ""
        self._visible_chars: int = 0

        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setFont(QFont("Segoe UI", 10))
        self._label.setStyleSheet("color: #2B2118; background: transparent;")
        self._label.setMaximumWidth(settings.speech_bubble.max_width - 24)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 18)  # extra bottom margin for the "tail"
        layout.addWidget(self._label)

        self._typing_timer = QTimer(self)
        self._typing_timer.timeout.connect(self._reveal_next_char)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        self.hide()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def say(self, text: str, anchor: QPoint) -> None:
        """
        Display `text` with a typing animation, positioned above `anchor`
        (typically the top-center point of the pet window, in global
        screen coordinates).
        """
        logger.debug("SpeechBubble.say(%r)", text)
        self._full_text = text
        self._visible_chars = 0
        self._label.setText("")

        self._reposition(anchor)
        self.show()
        self.raise_()

        self._typing_timer.start(settings.speech_bubble.typing_speed_ms)
        self._hide_timer.stop()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _reveal_next_char(self) -> None:
        self._visible_chars += 1
        self._label.setText(self._full_text[: self._visible_chars])
        self.adjustSize()

        if self._visible_chars >= len(self._full_text):
            self._typing_timer.stop()
            self._hide_timer.start(settings.speech_bubble.auto_hide_ms)

    def _reposition(self, anchor: QPoint) -> None:
        """Place the bubble roughly centered above the given anchor point."""
        self.adjustSize()
        x = anchor.x() - self.width() // 2
        y = anchor.y() - self.height() - 10
        self.move(x, y)

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt override)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        rect = self.rect().adjusted(0, 0, -1, -8)
        path = QPainterPath()
        path.addRoundedRect(rect, 14, 14)

        # Speech bubble "tail" pointing down toward the pet.
        tail_w = 14
        cx = rect.center().x()
        path.moveTo(cx - tail_w / 2, rect.bottom())
        path.lineTo(cx, rect.bottom() + 10)
        path.lineTo(cx + tail_w / 2, rect.bottom())
        path.closeSubpath()

        painter.setPen(QColor("#E0DDEA"))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawPath(path)
        painter.end()
