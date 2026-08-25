"""Safe, user-facing application error taxonomy."""

from enum import StrEnum


class ErrorCategory(StrEnum):
    CONFIGURATION = "configuration"
    INGESTION = "ingestion"
    INDEXING = "indexing"
    RETRIEVAL = "retrieval"
    PROVIDER = "provider"
    PERSISTENCE = "persistence"


class ApplicationError(Exception):
    def __init__(self, category: ErrorCategory, message: str, *, retryable=False):
        super().__init__(message)
        self.category = category
        self.retryable = retryable


def user_message(error: Exception) -> str:
    if isinstance(error, ApplicationError):
        action = " Try again or use Refresh Knowledge Base." if error.retryable else ""
        return f"{error.category.value.title()} error: {error}. {action}".strip()
    return "The request could not be completed. Check the service status and try again."
