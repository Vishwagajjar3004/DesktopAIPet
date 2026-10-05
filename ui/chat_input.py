"""
ui/chat_input.py
------------------
A small frameless text-entry popup used for chatting with Asha, plus a
matching "mic" trigger for voice input. Kept visually consistent with
`SpeechBubble` (rounded, translucent, no window chrome).
"""

from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from utils.logger import get_logger

logger = get_logger(__name__)


class ChatInput(QWidget):
    """Borderless input bar: [ mic ] [ text field ] that emits `message_submitted`."""

    message_submitted = Signal(str)
    mic_clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None, mic_available: bool = False) -> None:
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
        self.setFixedSize(260, 44)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        self._mic_button = QPushButton("🎤")
        self._mic_button.setFixedSize(28, 28)
        self._mic_button.setEnabled(mic_available)
        self._mic_button.setToolTip("Speak to Asha" if mic_available else "Microphone unavailable")
        self._mic_button.setStyleSheet(
            "QPushButton { border: none; background: transparent; font-size: 14px; }"
        )
        self._mic_button.clicked.connect(self.mic_clicked.emit)

        self._line_edit = QLineEdit()
        self._line_edit.setPlaceholderText("Say something to Asha...")
        self._line_edit.setStyleSheet(
            "QLineEdit { border: none; background: transparent; color: #2B2118; font-size: 12px; }"
        )
        self._line_edit.returnPressed.connect(self._submit)

        layout.addWidget(self._mic_button)
        layout.addWidget(self._line_edit)

        self.hide()

    def open_at(self, anchor: QPoint) -> None:
        self.move(anchor.x() - self.width() // 2, anchor.y())
        self.show()
        self.raise_()
        self._line_edit.setFocus()

    def set_text(self, text: str) -> None:
        self._line_edit.setText(text)

    def _submit(self) -> None:
        text = self._line_edit.text().strip()
        if not text:
            return
        self._line_edit.clear()
        self.hide()
        self.message_submitted.emit(text)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        path = QPainterPath()
        path.addRoundedRect(self.rect().adjusted(0, 0, -1, -1), 18, 18)
        painter.setPen(QColor("#E0DDEA"))
        painter.setBrush(QColor(255, 255, 255, 235))
        painter.drawPath(path)
        painter.end()

    def focusOutEvent(self, event) -> None:  # noqa: N802
        self.hide()
        super().focusOutEvent(event)
