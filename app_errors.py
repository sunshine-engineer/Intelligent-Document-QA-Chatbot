"""Define application error categories and safe user-facing recovery messages.

File: app_errors.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from enum import StrEnum


class ErrorCategory(StrEnum):
    """Stable diagnostic categories for configuration, ingestion, indexing,
    retrieval and provider failures.
    """

    CONFIGURATION = "configuration"
    INGESTION = "ingestion"
    INDEXING = "indexing"
    RETRIEVAL = "retrieval"
    PROVIDER = "provider"
    PERSISTENCE = "persistence"


class ApplicationError(Exception):
    """Expected application error carrying a safe message, diagnostic category and
    retry hint.
    """

    def __init__(self, category: ErrorCategory, message: str, *, retryable=False):
        """Initialize the safe application error and retry metadata.

        Args:
            category: Application error category used for safe display or
                correlated logging.
            message: User-safe application error text.
            retryable: Whether a user retry or knowledge-base refresh may
                recover the error.
        """
        super().__init__(message)
        self.category = category
        self.retryable = retryable


def user_message(error: Exception) -> str:
    """Format an expected application error or a generic safe fallback.

    Args:
        error: Exception to classify or report without exposing its raw payload.

    Returns:
        User-safe text with an optional recovery action.
    """
    if isinstance(error, ApplicationError):
        action = " Try again or use Refresh Knowledge Base." if error.retryable else ""
        return f"{error.category.value.title()} error: {error}. {action}".strip()
    return "The request could not be completed. Check the service status and try again."
