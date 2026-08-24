"""Application services used by the Streamlit adapter.

The services keep filesystem, vector-store, and retrieval orchestration out of
the UI module.  Dependencies are injectable so lifecycle behavior can be
tested without starting Streamlit or Ollama.
"""

import os
from dataclasses import dataclass
from typing import Any, Callable

from index_metadata import (
    build_index_manifest,
    build_index_metrics,
    get_document_manifest,
    get_pdf_state,
    load_index_manifest,
    load_metadata,
    save_faiss_index_atomically,
    save_index_manifest,
    save_metadata,
    verify_index_manifest,
    is_valid_index_metrics,
)


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
    ):
        self.config = config
        self.embedding_factory = embedding_factory
        self.loader_factory = loader_factory
        self.splitter_factory = splitter_factory
        self.faiss_loader = faiss_loader

    def load(self) -> tuple[Any, dict]:
        if not verify_index_manifest(
            self.config.index_directory,
            self.config.embedding_provider,
            self.config.embedding_model,
        ):
            raise ValueError("Saved FAISS index verification failed")

        vectors = self.faiss_loader(
            self.config.index_directory,
            self.embedding_factory(),
            allow_dangerous_deserialization=True,
        )
        manifest = load_index_manifest()
        if manifest.get("vector_dimension") != getattr(vectors.index, "d", None):
            raise ValueError("Saved FAISS index dimension verification failed")

        metadata = load_metadata() or {}
        metrics = metadata.get("metrics")
        if not is_valid_index_metrics(metrics):
            raise ValueError("Saved index metrics are unavailable")
        return vectors, metrics

    def build(self, document_changes=None, existing_vectors=None) -> tuple[Any, dict, list, list]:
        docs = self.loader_factory(self.config.pdf_directory).load()
        splitter = self.splitter_factory()
        vectors = existing_vectors
        documents_to_embed = docs

        if document_changes:
            added_or_changed = set(document_changes["added"]) | set(
                document_changes["changed"]
            )
            removed = set(document_changes["removed"])
            documents_to_remove = []
            for doc_id in vectors.index_to_docstore_id.values():
                document = vectors.docstore.search(doc_id)
                source = os.path.basename(document.metadata.get("source", ""))
                if source in added_or_changed or source in removed:
                    documents_to_remove.append(doc_id)
            if documents_to_remove:
                vectors.delete(documents_to_remove)
            documents_to_embed = [
                doc for doc in docs
                if os.path.basename(doc.metadata.get("source", ""))
                in added_or_changed
            ]

        final_documents = splitter.split_documents(documents_to_embed)
        if vectors is None:
            # Import lazily so unit tests can inject a fake FAISS implementation.
            from langchain_community.vectorstores import FAISS
            vectors = FAISS.from_documents(final_documents, self.embedding_factory())
        elif final_documents:
            vectors.add_documents(final_documents)

        save_faiss_index_atomically(vectors, self.config.index_directory)
        document_manifest = get_document_manifest(self.config.pdf_directory)
        for document in document_manifest["documents"].values():
            document["status"] = "indexed"
        metrics = build_index_metrics(vectors, document_manifest)
        save_index_manifest(build_index_manifest(
            self.config.index_directory,
            self.config.embedding_provider,
            self.config.embedding_model,
            getattr(vectors.index, "d", None),
        ))
        save_metadata(get_pdf_state(self.config.pdf_directory), document_manifest, metrics)
        return vectors, metrics, docs, final_documents
