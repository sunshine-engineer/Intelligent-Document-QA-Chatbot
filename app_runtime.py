"""Synchronize a session with the compatible persisted knowledge-base generation.

File: app_runtime.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

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
    """Session vectors, persisted metrics and the active generation identity; empty
    when no PDFs exist.

    Attributes:
        vectors: Vector-store instance exposing the FAISS-compatible
            retrieval/persistence interface.
        metrics: Persisted metric value to validate against the supported
            schema.
        generation: Persisted creation timestamp used to match a loaded
            generation.
    """

    vectors: Any = None
    metrics: dict | None = None
    generation: str | None = None


def synchronize_index(service: IndexService, previous=None, *, force=False):
    """Reuse a compatible session generation, load verified state, or rebuild the
    corpus.

    Args:
        service: IndexService configured for this corpus and persisted index
            location.
        previous: Optional session KnowledgeBase eligible for reuse.
        force: Whether to bypass compatible state and rebuild the collection.

    Returns:
        KnowledgeBase containing vectors, metrics and generation, or empty
        state.

    Raises:
        OSError: Discovery or persistence access fails.
        Exception: Loader, provider or index-build failures propagate to the UI
            boundary.

    Notes:
        No failed build replaces the caller's session state. Empty input
        discards generated artifacts. Directory promotion is not a multi-writer
        protocol.
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
