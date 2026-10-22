"""Track PDF content identity and persist integrity-checked index generations.

File: index_metadata.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

METADATA_FILE = "vector_store/index_metadata.json"
INDEX_MANIFEST_FILE = "vector_store/index_manifest.json"
INDEX_SCHEMA_VERSION = 1
INDEX_ARTIFACTS = ("index.faiss", "index.pkl")
SNAPSHOT_FILE = "index_snapshot.json"
DOCUMENT_MANIFEST_SCHEMA_VERSION = 1
METRICS_SCHEMA_VERSION = 1


def get_pdf_files(pdf_directory):
    """List sorted top-level, non-hidden PDF files while tolerating a missing
    directory.

    Args:
        pdf_directory: Directory whose top-level non-hidden PDF files are
            inspected.

    Returns:
        Sorted PDF basenames, or an empty list for an absent input directory.
    """
    if not os.path.isdir(pdf_directory):
        return []

    return [
        filename
        for filename in sorted(os.listdir(pdf_directory))
        if filename.lower().endswith(".pdf")
        and not filename.startswith(".")
        and (Path(pdf_directory) / filename).is_file()
    ]


def get_document_manifest(pdf_directory):
    """Record each discovered PDF path, content checksum, size and discovery
    status.

    Args:
        pdf_directory: Directory whose top-level non-hidden PDF files are
            inspected.

    Returns:
        Versioned mapping of relative paths to checksum, size and status
        records.

    Raises:
        OSError: A discovered PDF cannot be read or inspected.
    """
    manifest = {}

    for filename in get_pdf_files(pdf_directory):
        path = Path(pdf_directory) / filename
        normalized_path = filename.replace(os.sep, "/")
        manifest[normalized_path] = {
            "path": normalized_path,
            "sha256": _sha256_file(path),
            "size": path.stat().st_size,
            "status": "discovered",
        }

    return {
        "schema_version": DOCUMENT_MANIFEST_SCHEMA_VERSION,
        "documents": manifest,
    }


def compare_document_manifests(previous, current):
    """Classify document additions, content changes, removals and unchanged paths.

    Args:
        previous: Prior document manifest or None for a new collection.
        current: Current discovered document manifest.

    Returns:
        Mapping with added, changed, unchanged and removed path lists.
    """
    previous_documents = (
        previous.get("documents", {}) if isinstance(previous, dict) else {}
    )
    current_documents = (
        current.get("documents", {}) if isinstance(current, dict) else {}
    )

    added = sorted(set(current_documents) - set(previous_documents))
    removed = sorted(set(previous_documents) - set(current_documents))
    changed = sorted(
        path
        for path in set(previous_documents) & set(current_documents)
        if previous_documents[path].get("sha256")
        != current_documents[path].get("sha256")
    )
    unchanged = sorted(
        path
        for path in set(previous_documents) & set(current_documents)
        if path not in changed
    )

    return {
        "added": added,
        "changed": changed,
        "unchanged": unchanged,
        "removed": removed,
    }


def build_index_metrics(chunks, document_manifest, indexed_at=None):
    """Count indexed documents and chunks and attach an indexing timestamp.

    Args:
        chunks: Final text-document chunks used to compute persisted metrics.
        document_manifest: Versioned source-file identity and status records.
        indexed_at: Optional timestamp override; defaults to the current UTC ISO
            timestamp.

    Returns:
        Versioned counts, per-document chunk counts and UTC indexing timestamp.
    """
    per_document_chunk_counts: dict[str, int] = {}
    for document in chunks:
        metadata = getattr(document, "metadata", {}) or {}
        source = metadata.get("source", "")
        source_name = os.path.basename(source).replace(os.sep, "/")
        per_document_chunk_counts[source_name] = (
            per_document_chunk_counts.get(source_name, 0) + 1
        )

    documents = (
        document_manifest.get("documents", {})
        if isinstance(document_manifest, dict)
        else {}
    )

    return {
        "schema_version": METRICS_SCHEMA_VERSION,
        "document_count": len(documents),
        "chunk_count": sum(per_document_chunk_counts.values()),
        "per_document_chunk_counts": per_document_chunk_counts,
        "indexed_at": indexed_at or datetime.now(timezone.utc).isoformat(),
    }


def is_valid_index_metrics(metrics):
    """Check the required schema version and field types of persisted index
    metrics.

    Args:
        metrics: Persisted metric value to validate against the supported
            schema.

    Returns:
        True when the documented compatibility/existence check passes; otherwise
        False.
    """
    return (
        isinstance(metrics, dict)
        and metrics.get("schema_version") == METRICS_SCHEMA_VERSION
        and isinstance(metrics.get("document_count"), int)
        and isinstance(metrics.get("chunk_count"), int)
        and isinstance(metrics.get("per_document_chunk_counts"), dict)
        and isinstance(metrics.get("indexed_at"), str)
    )


def get_pdf_state(pdf_directory):
    """Compute the content identity of the currently discovered PDF collection.

    Args:
        pdf_directory: Directory whose top-level non-hidden PDF files are
            inspected.

    Returns:
        Hexadecimal SHA-256 identity of the stable document fields.
    """
    return document_state(get_document_manifest(pdf_directory))


def document_state(manifest):
    """Hash stable document identity fields while excluding mutable processing
    status.

    Args:
        manifest: Versioned document or artifact manifest for the current
            operation.

    Returns:
        Hexadecimal SHA-256 identity independent of processing status.
    """
    documents = manifest.get("documents", {})
    identity = {
        name: {key: record.get(key) for key in ("path", "sha256", "size")}
        for name, record in documents.items()
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def _sha256_file(path):
    """Hash a file in bounded blocks without loading the whole artifact into
    memory.

    Args:
        path: Filesystem path to read or write.

    Returns:
        Hexadecimal SHA-256 digest of the artifact bytes.

    Raises:
        OSError: The input artifact cannot be opened or read.
    """
    digest = hashlib.sha256()

    with open(path, "rb") as file_handle:
        for block in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def build_index_manifest(
    index_directory,
    embedding_provider,
    embedding_model,
    vector_dimension,
):
    """Record provider identity, vector dimension and checksums of both index
    artifacts.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.
        vector_dimension: Embedding dimension recorded alongside the artifacts.

    Returns:
        JSON-compatible schema, provider, dimension, time and artifact records.

    Raises:
        FileNotFoundError: A required FAISS artifact is absent.
        OSError: An artifact cannot be inspected or hashed.
    """
    index_path = Path(index_directory)
    artifacts = {}

    for artifact_name in INDEX_ARTIFACTS:
        artifact_path = index_path / artifact_name
        if not artifact_path.is_file():
            raise FileNotFoundError(artifact_name)
        artifacts[artifact_name] = {
            "sha256": _sha256_file(artifact_path),
            "size": artifact_path.stat().st_size,
        }

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "vector_dimension": vector_dimension,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": artifacts,
    }


def _snapshot_path(index_directory):
    """Resolve the fixed snapshot filename below the configured index directory.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.

    Returns:
        Path to index_snapshot.json within the supplied index directory.
    """
    return Path(index_directory) / SNAPSHOT_FILE


def load_index_snapshot(index_directory):
    """Read snapshot JSON, returning no snapshot for missing, unreadable or
    malformed data.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.

    Returns:
        Decoded snapshot, or None when missing, unreadable or invalid JSON.
    """
    try:
        with open(_snapshot_path(index_directory), encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path, payload):
    """Write an indented UTF-8 JSON document with a terminating newline.

    Args:
        path: Filesystem path to read or write.
        payload: JSON-serializable data to write or POST.

    Returns:
        None.

    Raises:
        OSError: The destination cannot be written.
        TypeError: The payload is not JSON serializable.
    """
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2)
        file_handle.write("\n")


def build_index_snapshot(
    index_directory,
    embedding_provider,
    embedding_model,
    vector_dimension,
    document_manifest,
    chunks,
    indexed_at=None,
    indexing_config=None,
):
    """Combine artifact integrity, document identity, metrics and indexing
    configuration.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.
        vector_dimension: Embedding dimension recorded alongside the artifacts.
        document_manifest: Versioned source-file identity and status records.
        chunks: Final text-document chunks used to compute persisted metrics.
        indexed_at: Optional timestamp override; defaults to the current UTC ISO
            timestamp.
        indexing_config: Optional splitter revision and chunk settings stored
            with the snapshot.

    Returns:
        Complete JSON-compatible generation record including metrics.
    """
    metrics = build_index_metrics(chunks, document_manifest, indexed_at)
    snapshot = build_index_manifest(
        index_directory, embedding_provider, embedding_model, vector_dimension
    )
    snapshot.update(
        {
            "snapshot_schema_version": 1,
            "pdf_state": document_state(document_manifest),
            "document_manifest": document_manifest,
            "metrics": metrics,
            "indexing_config": indexing_config,
        }
    )
    return snapshot


def verify_index_snapshot(index_directory, embedding_provider, embedding_model):
    """Validate snapshot shape and both artifact checksums for the expected
    embedding model.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.

    Returns:
        True when the documented compatibility/existence check passes; otherwise
        False.
    """
    snapshot = load_index_snapshot(index_directory)
    if not isinstance(snapshot, dict) or snapshot.get("snapshot_schema_version") != 1:
        return False
    if not is_valid_index_metrics(snapshot.get("metrics")):
        return False
    document_manifest = snapshot.get("document_manifest")
    if not isinstance(document_manifest, dict):
        return False
    documents = document_manifest.get("documents")
    if not isinstance(documents, dict):
        return False
    return _verify_manifest(
        index_directory, embedding_provider, embedding_model, snapshot
    )


def _verify_manifest(index_directory, embedding_provider, embedding_model, manifest):
    """Compare persisted schema, provider identity, artifact sizes and content
    hashes.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.
        manifest: Versioned document or artifact manifest for the current
            operation.

    Returns:
        True when the documented compatibility/existence check passes; otherwise
        False.
    """
    if manifest.get("schema_version") != INDEX_SCHEMA_VERSION:
        return False
    if manifest.get("embedding_provider") != embedding_provider:
        return False
    if manifest.get("embedding_model") != embedding_model:
        return False
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict):
        return False
    index_path = Path(index_directory)
    for artifact_name in INDEX_ARTIFACTS:
        artifact_metadata = artifacts.get(artifact_name)
        artifact_path = index_path / artifact_name
        if not isinstance(artifact_metadata, dict) or not artifact_path.is_file():
            return False
        if artifact_metadata.get("size") != artifact_path.stat().st_size:
            return False
        if artifact_metadata.get("sha256") != _sha256_file(artifact_path):
            return False
    return True


def save_index_manifest(manifest):
    """Replace the legacy manifest JSON through a sibling temporary file.

    Args:
        manifest: Versioned document or artifact manifest for the current
            operation.

    Returns:
        None.

    Raises:
        OSError: The legacy manifest cannot be written or replaced.
    """
    manifest_path = Path(INDEX_MANIFEST_FILE)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(".tmp")

    with open(temporary_path, "w", encoding="utf-8") as file_handle:
        json.dump(manifest, file_handle, indent=2)
        file_handle.write("\n")

    os.replace(temporary_path, manifest_path)


def load_index_manifest():
    """Read legacy manifest JSON or return no manifest when it cannot be decoded.

    Returns:
        Decoded legacy manifest, or None on read/JSON errors.
    """
    try:
        with open(INDEX_MANIFEST_FILE, encoding="utf-8") as file_handle:
            return json.load(file_handle)
    except (OSError, json.JSONDecodeError):
        return None


def verify_index_manifest(
    index_directory,
    embedding_provider,
    embedding_model,
):
    """Verify the current snapshot, falling back to legacy manifest verification.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.

    Returns:
        True when the documented compatibility/existence check passes; otherwise
        False.
    """
    snapshot = load_index_snapshot(index_directory)
    if isinstance(snapshot, dict):
        return verify_index_snapshot(
            index_directory, embedding_provider, embedding_model
        )
    manifest = load_index_manifest()

    if not isinstance(manifest, dict):
        return False

    return _verify_manifest(
        index_directory, embedding_provider, embedding_model, manifest
    )


def save_index_snapshot_atomically(
    vectors,
    index_directory,
    embedding_provider,
    embedding_model,
    document_manifest,
    chunks,
    indexing_config=None,
):
    """Stage and verify a complete generation before promoting it with rollback on
    failure.

    Args:
        vectors: Vector-store instance exposing the FAISS-compatible
            retrieval/persistence interface.
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.
        embedding_provider: Expected embedding provider identity, such as
            ollama.
        embedding_model: Expected embedding model name; equality does not detect
            mutable-tag weight changes.
        document_manifest: Versioned source-file identity and status records.
        chunks: Final text-document chunks used to compute persisted metrics.
        indexing_config: Optional splitter revision and chunk settings stored
            with the snapshot.

    Returns:
        Snapshot record associated with the successfully promoted generation.

    Raises:
        Exception: Staging, verification or promotion fails; rollback is
            attempted before propagation.

    Notes:
        The target must be a child of a writable mount, not its mount point.
        This process-local rollback scheme does not provide concurrent-writer
        safety.
    """
    index_path = Path(index_directory)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(
        tempfile.mkdtemp(prefix=f".{index_path.name}.", dir=index_path.parent)
    )
    backup_path = index_path.with_name(f".{index_path.name}.backup")
    try:
        vectors.save_local(str(temporary_path))
        snapshot = build_index_snapshot(
            temporary_path,
            embedding_provider,
            embedding_model,
            getattr(vectors.index, "d", None),
            document_manifest,
            chunks,
            indexing_config=indexing_config,
        )
        _write_json(temporary_path / SNAPSHOT_FILE, snapshot)
        if not verify_index_snapshot(
            temporary_path, embedding_provider, embedding_model
        ):
            raise ValueError("Staged index snapshot verification failed")
        if backup_path.exists():
            shutil.rmtree(backup_path)
        if index_path.exists():
            os.replace(index_path, backup_path)
        os.replace(temporary_path, index_path)
        if backup_path.exists():
            shutil.rmtree(backup_path)
        return snapshot
    except Exception:
        if index_path.exists() and backup_path.exists():
            shutil.rmtree(index_path)
        if backup_path.exists() and not index_path.exists():
            os.replace(backup_path, index_path)
        raise
    finally:
        if temporary_path.exists():
            shutil.rmtree(temporary_path)


def save_faiss_index_atomically(vectors, index_directory):
    """Stage and replace legacy FAISS artifacts while restoring the previous
    directory on error.

    Args:
        vectors: Vector-store instance exposing the FAISS-compatible
            retrieval/persistence interface.
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.

    Returns:
        None.

    Raises:
        Exception: Staging or promotion fails; rollback is attempted before
            propagation.
    """
    index_path = Path(index_directory)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = Path(
        tempfile.mkdtemp(prefix=f".{index_path.name}.", dir=index_path.parent)
    )
    backup_path = index_path.with_name(f".{index_path.name}.backup")

    try:
        vectors.save_local(str(temporary_path))

        if backup_path.exists():
            shutil.rmtree(backup_path)
        if index_path.exists():
            os.replace(index_path, backup_path)

        os.replace(temporary_path, index_path)

        if backup_path.exists():
            shutil.rmtree(backup_path)
    except Exception:
        if index_path.exists() and backup_path.exists():
            shutil.rmtree(index_path)
        if backup_path.exists() and not index_path.exists():
            os.replace(backup_path, index_path)
        raise
    finally:
        if temporary_path.exists():
            shutil.rmtree(temporary_path)


def discard_persisted_index(index_directory):
    """Remove generated index data and the legacy manifest without removing source
    PDFs.

    Args:
        index_directory: Trusted generated index directory; must be below a
            replaceable mount root.

    Returns:
        None.

    Raises:
        OSError: Generated artifacts cannot be removed.
    """
    index_path = Path(index_directory)
    if index_path.exists():
        shutil.rmtree(index_path)

    manifest_path = Path(INDEX_MANIFEST_FILE)
    if manifest_path.exists():
        manifest_path.unlink()


def metadata_exists():
    """Report whether the legacy metadata file exists.

    Returns:
        True when the documented compatibility/existence check passes; otherwise
        False.
    """
    return os.path.exists(METADATA_FILE)


def load_metadata():
    """Read legacy metadata when present; malformed JSON and read failures
    propagate.

    Returns:
        Decoded legacy metadata, or None if the metadata file is absent.

    Raises:
        OSError: Existing legacy metadata cannot be read.
        json.JSONDecodeError: Existing legacy metadata is malformed.
    """
    if not metadata_exists():
        return None

    with open(METADATA_FILE) as f:
        return json.load(f)


def save_metadata(state, document_manifest=None, metrics=None):
    """Replace legacy PDF state and optional manifest/metrics through a temporary
    file.

    Args:
        state: Stable PDF state hash stored in the legacy metadata record.
        document_manifest: Versioned source-file identity and status records.
        metrics: Persisted metric value to validate against the supported
            schema.

    Returns:
        None.

    Raises:
        OSError: Legacy metadata cannot be written or replaced.
    """
    metadata_path = Path(METADATA_FILE)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = metadata_path.with_suffix(".tmp")
    payload = {"pdf_state": state}

    if document_manifest is not None:
        payload["document_manifest"] = document_manifest
    if metrics is not None:
        payload["metrics"] = metrics

    with open(temporary_path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2)
        file_handle.write("\n")

    os.replace(temporary_path, metadata_path)
