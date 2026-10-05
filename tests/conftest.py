"""
tests/conftest.py
--------------------
Shared pytest fixtures: a headless QApplication (required by any test
touching PySide6 widgets) and a scratch MemoryDB that doesn't touch the
real user database file.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Must be set before PySide6 creates any window on a display-less CI box.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv)
    yield app


@pytest.fixture
def temp_db_path(tmp_path):
    return tmp_path / "test_asha.db"


@pytest.fixture
def memory_db(temp_db_path):
    from database.memory_db import MemoryDB

    return MemoryDB(db_path=temp_db_path)
