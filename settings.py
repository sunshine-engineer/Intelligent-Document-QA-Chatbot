"""Validated application configuration."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping

DEFAULT_GROQ_MODEL = "openai/gpt-oss-20b"
DEFAULT_EMBEDDING_MODEL = "nomic-embed-text:latest"


@dataclass(frozen=True)
class Settings:
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

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None):
        env = os.environ if environ is None else environ
        parse_errors: list[str] = []

        def integer(name: str, default: int) -> int:
            try:
                return int(env.get(name, str(default)))
            except ValueError:
                parse_errors.append(f"{name} must be an integer.")
                return default

        def decimal(name: str, default: float) -> float:
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
            parse_errors=tuple(parse_errors),
        )

    def validate(self) -> list[str]:
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
        return errors

    @property
    def missing_credentials(self) -> list[str]:
        return ["GROQ_API_KEY"] if not self.groq_api_key else []

    def redacted_summary(self) -> dict[str, str | int | float]:
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
        }


def provider_guidance(error: Exception) -> str:
    """Return actionable guidance without exposing credentials."""
    text = str(error).lower()
    if any(marker in text for marker in ("401", "403", "auth", "api key")):
        return "Groq authentication failed. Verify GROQ_API_KEY and restart the app."
    if any(marker in text for marker in ("404", "not found", "model")):
        return "The configured model is unavailable. Choose an available LLM_MODEL."
    if any(marker in text for marker in ("timeout", "timed out")):
        return "The provider timed out. Retry shortly and verify network availability."
    if any(marker in text for marker in ("ollama", "connection refused", "connect")):
        return "Ollama is unavailable. Start Ollama and verify OLLAMA_HOST."
    return "The provider request failed. Verify the configured provider and model."
