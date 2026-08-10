"""
Centralized logger. Import `get_logger(__name__)` anywhere in the app.
Logs to stdout (captured by Docker/systemd) and to a rotating file.
"""
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(settings.log_level.upper())

    formatter = logging.Formatter(_FORMAT)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=5_000_000, backupCount=5
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
