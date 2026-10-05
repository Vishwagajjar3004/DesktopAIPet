"""
utils/history_export.py
--------------------------
Export helpers for the History Panel (Feature 9: TXT / CSV / JSON export).

Kept as plain functions operating on `MessageLogEntry` lists so they're
trivially unit-testable without touching Qt.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from database.memory_db import MessageLogEntry


def export_txt(entries: Iterable[MessageLogEntry], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(f"[{e.timestamp}] ({e.category}) {e.message}\n")


def export_csv(entries: Iterable[MessageLogEntry], path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "timestamp", "category", "message", "screen_time", "mood"])
        for e in entries:
            writer.writerow([e.id, e.timestamp, e.category, e.message, e.screen_time, e.mood])


def export_json(entries: Iterable[MessageLogEntry], path: Path) -> None:
    data = [
        {
            "id": e.id,
            "timestamp": e.timestamp,
            "category": e.category,
            "message": e.message,
            "screen_time": e.screen_time,
            "mood": e.mood,
        }
        for e in entries
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


EXPORTERS = {
    "txt": export_txt,
    "csv": export_csv,
    "json": export_json,
}
