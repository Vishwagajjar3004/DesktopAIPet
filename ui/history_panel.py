"""
ui/history_panel.py
----------------------
The History Panel (Features 4/8/9/10): every message the pet has ever
said, newest first, with search, category filtering, a Today/Yesterday/
Last 7 Days/Last 30 Days/All Time timeline filter, export to
TXT/CSV/JSON, and a Clear History action — styled dark, rounded, with a
light fade-in on open.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QPropertyAnimation, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from database.memory_db import MESSAGE_CATEGORIES, MemoryDB, MessageLogEntry
from utils.history_export import EXPORTERS
from utils.logger import get_logger

logger = get_logger(__name__)

_DATE_FILTERS = ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "All Time"]

# Category -> accent color for the little badge shown next to each message.
_CATEGORY_COLORS = {
    "Health": "#4CAF93",
    "Break Reminder": "#E0A02B",
    "Screen Time": "#5B8DEF",
    "Focus": "#7C6CF0",
    "Compliment": "#E85D9C",
    "Motivation": "#F0664C",
    "Productivity": "#3FBF8F",
    "Water Reminder": "#3FC1D6",
    "Exercise": "#D6603F",
    "General": "#8A8FA3",
}

_DARK_STYLESHEET = """
QDialog {
    background-color: #1E1B29;
    border-radius: 16px;
}
QLabel { color: #E7E4F0; }
QLineEdit, QComboBox {
    background-color: #2A2638;
    color: #E7E4F0;
    border: 1px solid #3D3852;
    border-radius: 10px;
    padding: 6px 10px;
}
QComboBox QAbstractItemView {
    background-color: #2A2638;
    color: #E7E4F0;
    selection-background-color: #4B3F72;
}
QListWidget {
    background-color: #241F33;
    border: 1px solid #3D3852;
    border-radius: 12px;
    padding: 6px;
}
QListWidget::item {
    border-radius: 8px;
    padding: 4px;
    margin: 2px;
}
QListWidget::item:selected {
    background-color: #35304A;
}
QPushButton {
    background-color: #4B3F72;
    color: #FFFFFF;
    border: none;
    border-radius: 10px;
    padding: 7px 16px;
}
QPushButton:hover { background-color: #5A4C8A; }
QPushButton#danger { background-color: #7A3B3B; }
QPushButton#danger:hover { background-color: #934747; }
"""


class HistoryPanel(QDialog):
    """Dark, rounded History Panel dialog showing everything the pet has said."""

    def __init__(self, memory_db: MemoryDB, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._memory_db = memory_db
        self._current_entries: list[MessageLogEntry] = []

        self.setWindowTitle("Asha — Message History")
        self.setMinimumSize(480, 560)
        self.setStyleSheet(_DARK_STYLESHEET)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(10)

        title = QLabel("🕘 Message History")
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        root.addWidget(title)

        # -- Filter row 1: search --------------------------------------
        self._search_box = QLineEdit()
        self._search_box.setPlaceholderText("Search messages…")
        self._search_box.textChanged.connect(self._refresh)
        root.addWidget(self._search_box)

        # -- Filter row 2: category + date range -------------------------
        filter_row = QHBoxLayout()
        self._category_combo = QComboBox()
        self._category_combo.addItem("All Categories", userData="All")
        for cat in MESSAGE_CATEGORIES:
            self._category_combo.addItem(cat, userData=cat)
        self._category_combo.currentIndexChanged.connect(self._refresh)
        filter_row.addWidget(self._category_combo, 1)

        self._date_combo = QComboBox()
        for label in _DATE_FILTERS:
            self._date_combo.addItem(label)
        self._date_combo.currentIndexChanged.connect(self._refresh)
        filter_row.addWidget(self._date_combo, 1)
        root.addLayout(filter_row)

        # -- Scrollable message list --------------------------------------
        self._list_widget = QListWidget()
        self._list_widget.setSpacing(2)
        root.addWidget(self._list_widget, 1)

        self._empty_label = QLabel("No messages yet.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #8A8FA3; padding: 24px;")
        self._empty_label.hide()
        root.addWidget(self._empty_label)

        # -- Bottom action row --------------------------------------------
        button_row = QHBoxLayout()

        clear_button = QPushButton("🗑️ Clear History")
        clear_button.setObjectName("danger")
        clear_button.clicked.connect(self._on_clear_history)
        button_row.addWidget(clear_button)

        export_button = QPushButton("⬇️ Export")
        export_menu = QMenu(export_button)
        export_menu.addAction("Export as TXT", lambda: self._on_export("txt"))
        export_menu.addAction("Export as CSV", lambda: self._on_export("csv"))
        export_menu.addAction("Export as JSON", lambda: self._on_export("json"))
        export_button.setMenu(export_menu)
        button_row.addWidget(export_button)

        button_row.addStretch(1)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_row.addWidget(close_button)

        root.addLayout(button_row)

        self._refresh()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _date_bounds(self) -> tuple[Optional[str], Optional[str]]:
        """Return (since_iso, until_iso) for the selected timeline filter."""
        choice = self._date_combo.currentText()
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if choice == "Today":
            return today_start.isoformat(), None
        if choice == "Yesterday":
            yesterday_start = today_start - timedelta(days=1)
            return yesterday_start.isoformat(), today_start.isoformat()
        if choice == "Last 7 Days":
            return (today_start - timedelta(days=7)).isoformat(), None
        if choice == "Last 30 Days":
            return (today_start - timedelta(days=30)).isoformat(), None
        return None, None  # "All Time"

    def _refresh(self) -> None:
        category = self._category_combo.currentData() or "All"
        search = self._search_box.text().strip() or None
        since_iso, until_iso = self._date_bounds()

        entries = self._memory_db.get_message_logs(
            category=category, search=search, since_iso=since_iso, until_iso=until_iso
        )
        self._current_entries = entries

        self._list_widget.clear()
        self._empty_label.setVisible(not entries)
        self._list_widget.setVisible(bool(entries))

        for entry in entries:
            item = QListWidgetItem()
            widget = self._build_row_widget(entry)
            item.setSizeHint(widget.sizeHint())
            self._list_widget.addItem(item)
            self._list_widget.setItemWidget(item, widget)

    def _build_row_widget(self, entry: MessageLogEntry) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(2)

        header = QHBoxLayout()
        time_label = QLabel(self._format_time(entry.timestamp))
        time_label.setStyleSheet("color: #A9A5C0; font-size: 11px;")
        header.addWidget(time_label)

        color = _CATEGORY_COLORS.get(entry.category, "#8A8FA3")
        badge = QLabel(entry.category)
        badge.setStyleSheet(
            f"background-color: {color}; color: white; border-radius: 8px; "
            f"padding: 1px 8px; font-size: 10px; font-weight: 600;"
        )
        header.addWidget(badge)
        header.addStretch(1)
        layout.addLayout(header)

        message_label = QLabel(entry.message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(message_label)

        return row

    @staticmethod
    def _format_time(iso_timestamp: str) -> str:
        try:
            dt = datetime.fromisoformat(iso_timestamp).astimezone()
            return dt.strftime("%I:%M %p, %d %b")
        except ValueError:
            return iso_timestamp

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _on_clear_history(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Clear History",
            "This will permanently delete all saved messages. Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self._memory_db.clear_message_logs()
            logger.info("Message history cleared by user.")
            self._refresh()

    def _on_export(self, fmt: str) -> None:
        if not self._current_entries:
            QMessageBox.information(self, "Export", "There's nothing to export with the current filters.")
            return

        default_name = f"asha_history.{fmt}"
        path_str, _ = QFileDialog.getSaveFileName(self, "Export History", default_name, f"*.{fmt}")
        if not path_str:
            return

        try:
            EXPORTERS[fmt](self._current_entries, Path(path_str))
            QMessageBox.information(self, "Export", f"History exported to:\n{path_str}")
            logger.info("History exported to %s (%s, %d entries)", path_str, fmt, len(self._current_entries))
        except OSError as exc:
            logger.exception("Failed to export history")
            QMessageBox.warning(self, "Export failed", str(exc))

    # ------------------------------------------------------------------
    # Fade-in animation
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # noqa: N802 (Qt override)
        super().showEvent(event)
        if QGuiApplication.platformName().startswith("wayland"):
            return
        self.setWindowOpacity(0.0)
        self._fade_anim = QPropertyAnimation(self, b"windowOpacity")
        self._fade_anim.setDuration(180)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.start()
