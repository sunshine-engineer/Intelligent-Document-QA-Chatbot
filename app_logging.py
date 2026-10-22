"""Configure correlated, rotated application logging without raw exception payloads.

File: app_logging.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import logging
import re
import uuid
from logging.handlers import RotatingFileHandler
from pathlib import Path

LOGGER = logging.getLogger("rag_assistant")


def configure_logging(
    log_directory="logs", *, max_bytes=5 * 1024 * 1024, backup_count=3
):
    """Install stderr and rotated file handlers once for the application logger.

    Args:
        log_directory: Directory receiving the application log and its rotated
            backups.
        max_bytes: Positive file-size threshold at which the handler rotates its
            current log.
        backup_count: Number of rotated log files retained by the handler.

    Returns:
        None.

    Raises:
        OSError: The log directory or file cannot be created.
    """
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
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        LOGGER.addHandler(handler)
        LOGGER.addHandler(file_handler)
        LOGGER.setLevel(logging.INFO)


def new_correlation_id() -> str:
    """Create a short opaque request reference without embedding user content.

    Returns:
        Twelve lowercase hexadecimal characters from a random UUID.
    """
    return uuid.uuid4().hex[:12]


def log_exception(correlation_id: str, category: str, error: Exception):
    """Log exception type and correlation context while omitting messages and
    tracebacks.

    Args:
        correlation_id: Optional opaque reference linking request and diagnostic
            events.
        category: Application error category used for safe display or correlated
            logging.
        error: Exception to classify or report without exposing its raw payload.

    Returns:
        None.
    """
    LOGGER.error(
        "operation failed error_type=%s",
        type(error).__name__,
        extra={"correlation_id": correlation_id, "category": category},
    )


def log_event(
    level: int, message: str, *, correlation_id="system", category="app", **context
):
    """Emit a structured event with redacted, length-bounded context values.

    Args:
        level: Standard-library logging severity.
        message: Safe event label; do not pass raw prompt or exception payloads.
        correlation_id: Optional opaque reference linking request and diagnostic
            events.
        category: Application error category used for safe display or correlated
            logging.
        **context: Additional safe event fields; recognized credential patterns
            are redacted.

    Returns:
        None.
    """
    LOGGER.log(
        level,
        "%s %s",
        message,
        " ".join(f"{key}={_redact(str(value))}" for key, value in context.items()),
        extra={"correlation_id": correlation_id, "category": category},
    )


def _redact(value: str) -> str:
    """Mask recognized credential patterns and bound the emitted diagnostic text.

    Args:
        value: Diagnostic or configuration value to inspect.

    Returns:
        Redacted text truncated to the diagnostic length bound.
    """
    redacted = re.sub(
        r"(?i)(GROQ_API_KEY|OPENAI_API_KEY)\s*[:=]\s*[^\s,;}]+",
        r"\1=[REDACTED]",
        value,
    )
    redacted = re.sub(
        r"(?i)Authorization\s*[:=]\s*[^,;}]+",
        "Authorization=[REDACTED]",
        redacted,
    )
    # Provider errors can include serialized request payloads. Keep the
    # diagnostic type/summary while preventing full prompts or documents from
    # becoming durable log content.
    return redacted[:1000]
