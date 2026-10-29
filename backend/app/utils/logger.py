"""
Structured logging module with redaction of sensitive credentials and secrets.
"""
import json
import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict

from app.config import settings

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

# Patterns that match potential secrets to redact
SECRET_PATTERNS = [
    (re.compile(r"(access_token|refresh_token|client_secret|bot_token|service_token|password|secret|authorization)[:=]\s*['\"]?([a-zA-Z0-9_\-\.\:\/]+)['\"]?", re.IGNORECASE), r"\1=***REDACTED***"),
    (re.compile(r"(Bearer\s+)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"(token=)([a-zA-Z0-9_\-\.]+)", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"bot\d+:[a-zA-Z0-9_\-]+", re.IGNORECASE), r"bot***REDACTED***"),
]


def redact_text(text: str) -> str:
    """Mask credentials and tokens in log messages."""
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern, repl in SECRET_PATTERNS:
        redacted = pattern.sub(repl, redacted)
    return redacted


class RedactingFormatter(logging.Formatter):
    """Plain-text formatter with redaction."""

    def format(self, record: logging.LogRecord) -> str:
        record.msg = redact_text(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact_text(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, (tuple, list)):
                record.args = tuple(redact_text(str(arg)) for arg in record.args)
        return super().format(record)


class JsonRedactingFormatter(logging.Formatter):
    """JSON structured formatter with secret redaction."""

    def format(self, record: logging.LogRecord) -> str:
        msg = redact_text(record.getMessage())
        log_obj: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": msg,
        }
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "props"):
            log_obj.update(record.props)
        return json.dumps(log_obj)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    if settings.log_format.lower() == "json":
        formatter = JsonRedactingFormatter()
    else:
        text_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        formatter = RedactingFormatter(text_format)

    # Console handler
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Rotating file handler
    file_handler = RotatingFileHandler(
        LOG_DIR / "app.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False
    return logger
