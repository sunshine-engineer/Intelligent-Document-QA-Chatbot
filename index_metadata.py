import os
import json
import hashlib
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

METADATA_FILE = "vector_store/index_metadata.json"
INDEX_MANIFEST_FILE = "vector_store/index_manifest.json"
INDEX_SCHEMA_VERSION = 1
INDEX_ARTIFACTS = ("index.faiss", "index.pkl")
DOCUMENT_MANIFEST_SCHEMA_VERSION = 1
METRICS_SCHEMA_VERSION = 1


def get_pdf_files(pdf_directory):

    if not os.path.isdir(pdf_directory):
        return []

    return [
        filename
        for filename in sorted(os.listdir(pdf_directory))
        if filename.lower().endswith(".pdf")
    ]


def get_document_manifest(pdf_directory):

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


def build_index_metrics(vectors, document_manifest):

    per_document_chunk_counts: dict[str, int] = {}
    index_to_docstore_id = getattr(vectors, "index_to_docstore_id", {})

    for document_id in index_to_docstore_id.values():
        document = vectors.docstore.search(document_id)
        source = document.metadata.get("source", "") if document else ""
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
        "chunk_count": len(index_to_docstore_id),
        "per_document_chunk_counts": per_document_chunk_counts,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


def is_valid_index_metrics(metrics):

    return (
        isinstance(metrics, dict)
        and metrics.get("schema_version") == METRICS_SCHEMA_VERSION
        and isinstance(metrics.get("document_count"), int)
        and isinstance(metrics.get("chunk_count"), int)
        and isinstance(metrics.get("per_document_chunk_counts"), dict)
        and isinstance(metrics.get("indexed_at"), str)
    )


def get_pdf_state(pdf_directory):

    text = json.dumps(get_document_manifest(pdf_directory), sort_keys=True)

    return hashlib.sha256(text.encode()).hexdigest()


def _sha256_file(path):

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


def save_index_manifest(manifest):

    manifest_path = Path(INDEX_MANIFEST_FILE)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = manifest_path.with_suffix(".tmp")

    with open(temporary_path, "w", encoding="utf-8") as file_handle:
        json.dump(manifest, file_handle, indent=2)
        file_handle.write("\n")

    os.replace(temporary_path, manifest_path)


def load_index_manifest():

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

    manifest = load_index_manifest()

    if not isinstance(manifest, dict):
        return False

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


def save_faiss_index_atomically(vectors, index_directory):

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

    index_path = Path(index_directory)
    if index_path.exists():
        shutil.rmtree(index_path)

    manifest_path = Path(INDEX_MANIFEST_FILE)
    if manifest_path.exists():
        manifest_path.unlink()


def metadata_exists():

    return os.path.exists(METADATA_FILE)


def load_metadata():

    if not metadata_exists():
        return None

    with open(METADATA_FILE) as f:
        return json.load(f)


def save_metadata(state, document_manifest=None, metrics=None):

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
