"""Index lifecycle orchestration shared by the UI and regression checks."""

from dataclasses import dataclass
from typing import Any

from app_services import IndexService
from index_metadata import (
    discard_persisted_index,
    document_state,
    get_document_manifest,
    load_index_snapshot,
)


@dataclass
class KnowledgeBase:
    vectors: Any = None
    metrics: dict | None = None
    generation: str | None = None


def synchronize_index(service: IndexService, previous=None, *, force=False):
    """Reuse unchanged session vectors; load or build only when needed.

    Discovery and configuration errors propagate to the UI's safe error boundary.
    No failed operation replaces the caller's previous state.
    """
    manifest = get_document_manifest(service.config.pdf_directory)
    if not manifest["documents"]:
        discard_persisted_index(service.config.index_directory)
        return KnowledgeBase()
    saved = load_index_snapshot(service.config.index_directory)
    compatible = (
        isinstance(saved, dict)
        and saved.get("pdf_state") == document_state(manifest)
        and saved.get("indexing_config") == service.config.indexing_config()
        and saved.get("embedding_provider") == service.config.embedding_provider
        and saved.get("embedding_model") == service.config.embedding_model
    )
    if compatible and not force:
        generation = saved.get("created_at")
        if (
            previous
            and previous.vectors is not None
            and previous.generation == generation
        ):
            return previous
        try:
            vectors, metrics = service.load()
            return KnowledgeBase(vectors, metrics, generation)
        except (ValueError, OSError):
            # Invalid or incomplete saved artifacts are recoverable by rebuilding.
            pass
    vectors, metrics, _, _ = service.build()
    snapshot = load_index_snapshot(service.config.index_directory)
    return KnowledgeBase(vectors, metrics, snapshot["created_at"])
