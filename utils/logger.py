"""
utils/logger.py
----------------
Centralized logging configuration for the Desktop AI Pet application.

Every module in the project should obtain its logger via:

    from utils.logger import get_logger
    logger = get_logger(__name__)

This guarantees a single consistent log format across the whole app,
writes logs both to the console and to a rotating file under
``DesktopAIPet/logs/asha.log``, and avoids duplicate handlers being
attached if a module is imported multiple times.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from config.settings import LOG_FILE, LOGS_DIR

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root_logger() -> None:
    """Attach console + rotating file handlers to the root logger once."""
    global _configured
    if _configured:
        return

    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """
    Return a module-level logger configured with the app's standard
    handlers/formatting.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    _configure_root_logger()
    return logging.getLogger(name)
