"""Parse, validate and summarize environment-based application configuration.

File: settings.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"
DEFAULT_GROQ_API_BASE_URL = "https://api.groq.com/openai/v1"


@dataclass(frozen=True)
class Settings:
    """Validated application paths, provider settings and resource limits. Call
    validate() after parsing.

    Attributes:
        groq_api_key: Optional Groq credential; omitted from configuration
            summaries.
        llm_model: Groq generation model identifier.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.
        ollama_url: Base URL of the Ollama embedding service.
        pdf_directory: Directory whose top-level non-hidden PDF files are
            inspected.
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        chunk_size: Maximum characters requested per splitter chunk.
        chunk_overlap: Character overlap between adjacent splitter chunks.
        default_top_k: Initial UI retrieval count.
        max_top_k: Largest retrieval count permitted by the UI.
        relevance_threshold: Minimum relevance score retained as evidence.
        groq_api_base_url: Groq-compatible HTTP API root, without a completion
            suffix.
        groq_timeout_seconds: Per-request generation timeout in seconds.
        groq_max_retries: Maximum client retry count for generation requests.
        max_output_tokens: Maximum requested generation output tokens.
        embedding_timeout_seconds: Per-request embedding timeout in seconds.
        max_question_characters: Maximum question characters accepted by the UI.
        max_history_messages: Maximum recent messages considered for generation.
        max_history_characters: Character cap applied after selecting recent
            messages.
        max_context_characters: Shared evidence-text character budget before
            source labels.
        log_directory: Directory receiving the application log and its rotated
            backups.
        log_max_bytes: File-size rotation threshold for application logs in
            bytes.
        log_backup_count: Number of rotated application log files retained.
        parse_errors: Safe numeric parsing errors collected by from_env().
    """

    groq_api_key: str | None
    llm_model: str
    embedding_model: str
    ollama_url: str
    pdf_directory: Path
    index_directory: Path
    chunk_size: int
    chunk_overlap: int
    default_top_k: int
    max_top_k: int
    relevance_threshold: float
    parse_errors: tuple[str, ...] = ()
    groq_api_base_url: str = DEFAULT_GROQ_API_BASE_URL
    groq_timeout_seconds: float = 30.0
    groq_max_retries: int = 2
    max_output_tokens: int = 1024
    embedding_timeout_seconds: float = 60.0
    max_question_characters: int = 4000
    max_history_messages: int = 10
    max_history_characters: int = 6000
    max_context_characters: int = 16000
    log_directory: Path = Path("logs")
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 3

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None):
        """Parse a supplied environment without raising for malformed numeric
        configuration.

        Args:
            environ: Optional environment mapping; None reads os.environ without
                modifying it.

        Returns:
            Settings with numeric parsing errors collected for validate().
        """
        env = os.environ if environ is None else environ
        parse_errors: list[str] = []

        def integer(name: str, default: int) -> int:
            """Parse an integer setting while recording invalid input and using the
            fallback.

            Args:
                name: Environment variable name to read.
                default: Fallback value used when a variable is absent or cannot
                    be parsed.

            Returns:
                Parsed integer, or the provided default after a recorded parse
                failure.
            """
            try:
                return int(env.get(name, str(default)))
            except ValueError:
                parse_errors.append(f"{name} must be an integer.")
                return default

        def decimal(name: str, default: float) -> float:
            """Parse a numeric setting while recording invalid input and using the
            fallback.

            Args:
                name: Environment variable name to read.
                default: Fallback value used when a variable is absent or cannot
                    be parsed.

            Returns:
                Parsed float, or the provided default after a recorded parse
                failure.
            """
            try:
                return float(env.get(name, str(default)))
            except ValueError:
                parse_errors.append(f"{name} must be a number.")
                return default

        return cls(
            groq_api_key=env.get("GROQ_API_KEY") or None,
            llm_model=env.get("LLM_MODEL", DEFAULT_GROQ_MODEL),
            embedding_model=env.get("EMBEDDING_MODEL", DEFAULT_EMBEDDING_MODEL),
            ollama_url=env.get("OLLAMA_HOST", "http://ollama:11434"),
            pdf_directory=Path(env.get("PDF_DIRECTORY", "research_papers")),
            index_directory=Path(env.get("INDEX_DIRECTORY", "faiss_index")),
            chunk_size=integer("CHUNK_SIZE", 1000),
            chunk_overlap=integer("CHUNK_OVERLAP", 200),
            default_top_k=integer("DEFAULT_TOP_K", 4),
            max_top_k=integer("MAX_TOP_K", 10),
            relevance_threshold=decimal("RETRIEVAL_RELEVANCE_THRESHOLD", 0.35),
            groq_api_base_url=env.get("GROQ_API_BASE_URL", DEFAULT_GROQ_API_BASE_URL),
            groq_timeout_seconds=decimal("GROQ_TIMEOUT_SECONDS", 30.0),
            groq_max_retries=integer("GROQ_MAX_RETRIES", 2),
            max_output_tokens=integer("MAX_OUTPUT_TOKENS", 1024),
            embedding_timeout_seconds=decimal("EMBEDDING_TIMEOUT_SECONDS", 60.0),
            max_question_characters=integer("MAX_QUESTION_CHARACTERS", 4000),
            max_history_messages=integer("MAX_HISTORY_MESSAGES", 10),
            max_history_characters=integer("MAX_HISTORY_CHARACTERS", 6000),
            max_context_characters=integer("MAX_CONTEXT_CHARACTERS", 16000),
            log_directory=Path(env.get("LOG_DIRECTORY", "logs")),
            log_max_bytes=integer("LOG_MAX_BYTES", 5 * 1024 * 1024),
            log_backup_count=integer("LOG_BACKUP_COUNT", 3),
            parse_errors=tuple(parse_errors),
        )

    def validate(self) -> list[str]:
        """Collect configuration errors before any provider or filesystem work
        starts.

        Returns:
            List of safe validation messages; empty means locally valid
            settings.
        """
        errors = list(self.parse_errors)
        if not self.llm_model.strip():
            errors.append("LLM_MODEL must not be empty.")
        if not self.embedding_model.strip():
            errors.append("EMBEDDING_MODEL must not be empty.")
        if not self.ollama_url.strip():
            errors.append("OLLAMA_HOST must not be empty.")
        if self.chunk_size <= 0:
            errors.append("CHUNK_SIZE must be greater than zero.")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            errors.append("CHUNK_OVERLAP must be smaller than CHUNK_SIZE.")
        if self.max_top_k < 1:
            errors.append("MAX_TOP_K must be at least 1.")
        if self.default_top_k < 1 or self.default_top_k > self.max_top_k:
            errors.append("DEFAULT_TOP_K must be between 1 and MAX_TOP_K.")
        if not 0 <= self.relevance_threshold <= 1:
            errors.append("RETRIEVAL_RELEVANCE_THRESHOLD must be between 0 and 1.")
        if not self.groq_api_base_url.strip():
            errors.append("GROQ_API_BASE_URL must not be empty.")
        for name, value in (
            ("GROQ_TIMEOUT_SECONDS", self.groq_timeout_seconds),
            ("EMBEDDING_TIMEOUT_SECONDS", self.embedding_timeout_seconds),
        ):
            if not math.isfinite(value) or value <= 0:
                errors.append(f"{name} must be a finite number greater than zero.")
        for name, value in (
            ("MAX_OUTPUT_TOKENS", self.max_output_tokens),
            ("MAX_QUESTION_CHARACTERS", self.max_question_characters),
            ("MAX_HISTORY_MESSAGES", self.max_history_messages),
            ("MAX_HISTORY_CHARACTERS", self.max_history_characters),
            ("MAX_CONTEXT_CHARACTERS", self.max_context_characters),
            ("LOG_MAX_BYTES", self.log_max_bytes),
        ):
            if value < 1:
                errors.append(f"{name} must be at least 1.")
        if self.groq_max_retries < 0:
            errors.append("GROQ_MAX_RETRIES must not be negative.")
        if self.log_backup_count < 0:
            errors.append("LOG_BACKUP_COUNT must not be negative.")
        return errors

    @property
    def missing_credentials(self) -> list[str]:
        """List credentials required for generation that have not been configured.

        Returns:
            Missing generation credential names without credential values.
        """
        return ["GROQ_API_KEY"] if not self.groq_api_key else []

    def redacted_summary(self) -> dict[str, str | int | float]:
        """Return effective noncredential settings for UI inspection.

        Returns:
            Mapping of effective settings excluding GROQ_API_KEY.
        """
        return {
            "llm_model": self.llm_model,
            "embedding_model": self.embedding_model,
            "ollama_url": self.ollama_url,
            "pdf_directory": str(self.pdf_directory),
            "index_directory": str(self.index_directory),
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "default_top_k": self.default_top_k,
            "max_top_k": self.max_top_k,
            "relevance_threshold": self.relevance_threshold,
            "groq_api_base_url": self.groq_api_base_url,
            "groq_timeout_seconds": self.groq_timeout_seconds,
            "groq_max_retries": self.groq_max_retries,
            "max_output_tokens": self.max_output_tokens,
            "embedding_timeout_seconds": self.embedding_timeout_seconds,
            "max_question_characters": self.max_question_characters,
            "max_history_messages": self.max_history_messages,
            "max_history_characters": self.max_history_characters,
            "max_context_characters": self.max_context_characters,
            "log_directory": str(self.log_directory),
            "log_max_bytes": self.log_max_bytes,
            "log_backup_count": self.log_backup_count,
        }


def provider_guidance(error: Exception) -> str:
    """Map recognizable provider failures to actionable text without echoing the
    payload.

    Args:
        error: Exception to classify or report without exposing its raw payload.

    Returns:
        Safe recovery guidance selected from the error category.
    """
    text = str(error).lower()
    if any(marker in text for marker in ("401", "403", "auth", "api key")):
        return "Groq authentication failed. Verify GROQ_API_KEY and restart the app."
    if any(marker in text for marker in ("429", "rate limit", "quota")):
        return "Provider rate limit reached. Wait before retrying or check your quota."
    if any(marker in text for marker in ("404", "not found", "model")):
        return "The configured model is unavailable. Choose an available LLM_MODEL."
    if any(marker in text for marker in ("timeout", "timed out")):
        return "The provider timed out. Retry shortly and verify network availability."
    if any(marker in text for marker in ("ollama", "connection refused", "connect")):
        return "Ollama is unavailable. Start Ollama and verify OLLAMA_HOST."
    return "The provider request failed. Verify the configured provider and model."
