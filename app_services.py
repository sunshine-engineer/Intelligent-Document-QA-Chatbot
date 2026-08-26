"""Application services used by the Streamlit adapter.

The services keep filesystem, vector-store, and retrieval orchestration out of
the UI module.  Dependencies are injectable so lifecycle behavior can be
tested without starting Streamlit or Ollama.
"""

from dataclasses import dataclass
from typing import Any, Callable

from index_metadata import (
    get_document_manifest,
    load_index_snapshot,
    save_index_snapshot_atomically,
    verify_index_manifest,
    is_valid_index_metrics,
)
import logging
import time
from app_logging import log_event, new_correlation_id


@dataclass(frozen=True)
class IndexConfig:
    pdf_directory: str
    index_directory: str
    embedding_provider: str
    embedding_model: str


class IndexService:
    """Build and load a verified FAISS index without UI/session dependencies."""

    def __init__(
        self,
        config: IndexConfig,
        embedding_factory: Callable[[], Any],
        loader_factory: Callable[[str], Any],
        splitter_factory: Callable[[], Any],
        faiss_loader: Callable[..., Any],
        faiss_factory: Callable[[list[Any], Any], Any] | None = None,
    ):
        self.config = config
        self.embedding_factory = embedding_factory
        self.loader_factory = loader_factory
        self.splitter_factory = splitter_factory
        self.faiss_loader = faiss_loader
        self.faiss_factory = faiss_factory

    def load(self) -> tuple[Any, dict]:
        correlation_id = new_correlation_id()
        log_event(
            logging.INFO,
            "index_load_started",
            correlation_id=correlation_id,
            category="indexing",
            index_directory=self.config.index_directory,
        )
        if not verify_index_manifest(
            self.config.index_directory,
            self.config.embedding_provider,
            self.config.embedding_model,
        ):
            error = ValueError("Saved FAISS index verification failed")
            log_event(
                logging.WARNING,
                "index_verification_failed_rebuild_required",
                correlation_id=correlation_id,
                category="indexing",
                index_directory=self.config.index_directory,
                embedding_provider=self.config.embedding_provider,
                embedding_model=self.config.embedding_model,
            )
            raise error

        vectors = self.faiss_loader(
            self.config.index_directory,
            self.embedding_factory(),
            allow_dangerous_deserialization=True,
        )
        manifest = load_index_snapshot(self.config.index_directory)
        if not isinstance(manifest, dict):
            raise ValueError("Saved FAISS index manifest is unavailable")
        if manifest.get("vector_dimension") != getattr(vectors.index, "d", None):
            raise ValueError("Saved FAISS index dimension verification failed")

        metrics = manifest.get("metrics")
        if not is_valid_index_metrics(metrics):
            raise ValueError("Saved index metrics are unavailable")
        assert isinstance(metrics, dict)
        log_event(
            logging.INFO,
            "index_load_completed",
            correlation_id=correlation_id,
            category="indexing",
            document_count=metrics["document_count"],
            chunk_count=metrics["chunk_count"],
        )
        return vectors, metrics

    def build(
        self, document_changes=None, existing_vectors=None
    ) -> tuple[Any, dict, list, list]:
        correlation_id = new_correlation_id()
        started_at = time.perf_counter()
        # A persisted snapshot must contain metrics for the complete chunk set.
        # Rebuild the affected generation from explicit chunk records rather
        # than reading FAISS's private document-store mappings.
        incremental = False
        log_event(
            logging.INFO,
            "index_build_started",
            correlation_id=correlation_id,
            category="indexing",
            incremental=incremental,
            recovery_full_rebuild=bool(document_changes) and not incremental,
        )
        docs = self.loader_factory(self.config.pdf_directory).load()
        log_event(
            logging.INFO,
            "documents_loaded",
            correlation_id=correlation_id,
            category="ingestion",
            pages=len(docs),
        )
        splitter = self.splitter_factory()
        vectors = None
        documents_to_embed = docs

        final_documents = splitter.split_documents(documents_to_embed)
        log_event(
            logging.INFO,
            "documents_chunked",
            correlation_id=correlation_id,
            category="ingestion",
            chunks=len(final_documents),
        )
        if vectors is None:
            factory: Callable[[list[Any], Any], Any]
            if self.faiss_factory is None:
                # Backward-compatible lazy default for non-Streamlit callers.
                from langchain_community.vectorstores import FAISS

                factory = FAISS.from_documents
            else:
                factory = self.faiss_factory
            vectors = factory(final_documents, self.embedding_factory())
        elif final_documents:
            vectors.add_documents(final_documents)

        document_manifest = get_document_manifest(self.config.pdf_directory)
        for document in document_manifest["documents"].values():
            document["status"] = "indexed"
        snapshot = save_index_snapshot_atomically(
            vectors,
            self.config.index_directory,
            self.config.embedding_provider,
            self.config.embedding_model,
            document_manifest,
            final_documents,
        )
        metrics = snapshot["metrics"]
        log_event(
            logging.INFO,
            "index_build_completed",
            correlation_id=correlation_id,
            category="indexing",
            document_count=metrics["document_count"],
            chunk_count=metrics["chunk_count"],
            latency_ms=round((time.perf_counter() - started_at) * 1000, 2),
        )
        return vectors, metrics, docs, final_documents
