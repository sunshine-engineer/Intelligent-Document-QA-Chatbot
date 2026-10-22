"""Build and load verified FAISS indexes through injectable infrastructure adapters.

File: app_services.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from app_logging import log_event, new_correlation_id
from index_metadata import (
    document_state,
    get_document_manifest,
    is_valid_index_metrics,
    load_index_snapshot,
    save_index_snapshot_atomically,
    verify_index_manifest,
)


@dataclass(frozen=True)
class IndexConfig:
    """Immutable index inputs and splitter settings defining persisted-generation
    compatibility.

    Attributes:
        pdf_directory: Directory whose top-level non-hidden PDF files are
            inspected.
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.
        chunk_size: Maximum characters requested per splitter chunk.
        chunk_overlap: Character overlap between adjacent splitter chunks.
    """

    pdf_directory: str
    index_directory: str
    embedding_provider: str
    embedding_model: str
    chunk_size: int = 1000
    chunk_overlap: int = 200

    def indexing_config(self):
        """Return the splitter identity and chunk settings required for snapshot
        compatibility.

        Returns:
            JSON-compatible splitter revision and chunk-size/overlap settings.
        """
        return {
            "splitter": "RecursiveCharacterTextSplitter:v1",
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
        }


class IndexService:
    """Injectable index build/load orchestration; source PDFs and trusted generated
    state stay separate.
    """

    def __init__(
        self,
        config: IndexConfig,
        embedding_factory: Callable[[], Any],
        loader_factory: Callable[[str], Any],
        splitter_factory: Callable[[], Any],
        faiss_loader: Callable[..., Any],
        faiss_factory: Callable[[list[Any], Any], Any] | None = None,
    ):
        """Initialize injected adapters and state without performing provider
        requests.

        Args:
            config: Index paths, embedding identity and splitter compatibility
                settings.
            embedding_factory: Zero-argument callback returning an embedding
                client.
            loader_factory: Callback accepting a PDF directory and returning a
                document loader.
            splitter_factory: Zero-argument callback returning a document
                splitter.
            faiss_loader: Callback loading a persisted vector store after
                verification.
            faiss_factory: Optional callback embedding chunks into a new vector
                store.
        """
        self.config = config
        self.embedding_factory = embedding_factory
        self.loader_factory = loader_factory
        self.splitter_factory = splitter_factory
        self.faiss_loader = faiss_loader
        self.faiss_factory = faiss_factory

    def load(self) -> tuple[Any, dict]:
        """Verify snapshot compatibility and integrity before loading its FAISS
        document store.

        Returns:
            Tuple of verified vectors and their persisted metrics.

        Raises:
            ValueError: Integrity, dimension, metrics or indexing configuration
                is incompatible.
            Exception: Embedding construction or deserialization fails.
        """
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

        manifest = load_index_snapshot(self.config.index_directory)
        if not isinstance(manifest, dict):
            raise ValueError("Saved FAISS index manifest is unavailable")
        if manifest.get("indexing_config") != self.config.indexing_config():
            raise ValueError(
                "Saved FAISS chunk configuration changed; rebuild required"
            )
        vectors = self.faiss_loader(
            self.config.index_directory,
            self.embedding_factory(),
            allow_dangerous_deserialization=True,
        )
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
        """Fully parse, split, embed and persist a stable generation of the PDF
        collection.

        Args:
            document_changes: Optional legacy change classification used for
                diagnostics; builds remain full.
            existing_vectors: Legacy compatibility argument; never mutated or
                reused for incremental indexing.

        Returns:
            Tuple of vectors, metrics, loaded pages and final text chunks.

        Raises:
            ValueError: No text is extracted or PDFs change while the generation
                is being built.
            Exception: Parsing, embedding or persistence fails; a successful
                snapshot is not returned.
        """
        correlation_id = new_correlation_id()
        started_at = time.perf_counter()
        initial_manifest = get_document_manifest(self.config.pdf_directory)
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
        if not final_documents:
            raise ValueError(
                "No extractable text found. Use text-based, readable PDFs."
            )
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
        if document_state(initial_manifest) != document_state(document_manifest):
            raise ValueError("PDF files changed while indexing; retry the refresh")
        for document in document_manifest["documents"].values():
            document["status"] = "indexed"
        snapshot = save_index_snapshot_atomically(
            vectors,
            self.config.index_directory,
            self.config.embedding_provider,
            self.config.embedding_model,
            document_manifest,
            final_documents,
            indexing_config=self.config.indexing_config(),
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
