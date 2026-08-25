"""Correlation-aware logging with secret and content safeguards."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import uuid


LOGGER = logging.getLogger("rag_assistant")


def configure_logging(log_directory="logs"):
    if not LOGGER.handlers:
        Path(log_directory).mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s correlation_id=%(correlation_id)s "
            "category=%(category)s %(message)s"
        )
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        file_handler = RotatingFileHandler(
            Path(log_directory) / "app.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(handler)
        LOGGER.addHandler(file_handler)
        LOGGER.setLevel(logging.INFO)


def new_correlation_id() -> str:
    return uuid.uuid4().hex[:12]


def log_exception(correlation_id: str, category: str, error: Exception):
    LOGGER.error(
        "operation failed error_type=%s error=%s",
        type(error).__name__,
        _redact(str(error)),
        exc_info=(error.__class__, error, error.__traceback__)
        if error.__traceback__ is not None
        else False,
        extra={"correlation_id": correlation_id, "category": category},
    )


def log_event(level: int, message: str, *, correlation_id="system", category="app", **context):
    LOGGER.log(
        level,
        "%s %s",
        message,
        " ".join(f"{key}={_redact(str(value))}" for key, value in context.items()),
        extra={"correlation_id": correlation_id, "category": category},
    )


def _redact(value: str) -> str:
    for marker in ("GROQ_API_KEY=", "OPENAI_API_KEY=", "Authorization:"):
        if marker in value:
            return value.split(marker, 1)[0] + marker + "[REDACTED]"
    return value
