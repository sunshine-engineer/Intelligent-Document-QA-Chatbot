import os
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path

METADATA_FILE = "vector_store/index_metadata.json"
INDEX_MANIFEST_FILE = "vector_store/index_manifest.json"
INDEX_SCHEMA_VERSION = 1
INDEX_ARTIFACTS = ("index.faiss", "index.pkl")


def get_pdf_files(pdf_directory):

    if not os.path.isdir(pdf_directory):
        return []

    return [
        filename
        for filename in sorted(os.listdir(pdf_directory))
        if filename.lower().endswith(".pdf")
    ]


def get_pdf_state(pdf_directory):

    pdfs = []

    for filename in get_pdf_files(pdf_directory):

        path = os.path.join(pdf_directory, filename)

        stat = os.stat(path)

        pdfs.append({
            "file": filename,
            "size": stat.st_size,
            "mtime": stat.st_mtime,
        })

    text = json.dumps(pdfs, sort_keys=True)

    return hashlib.md5(text.encode()).hexdigest()


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


def metadata_exists():

    return os.path.exists(METADATA_FILE)


def load_metadata():

    if not metadata_exists():
        return None

    with open(METADATA_FILE) as f:
        return json.load(f)


def save_metadata(state):

    os.makedirs("vector_store", exist_ok=True)

    with open(METADATA_FILE, "w") as f:

        json.dump(
            {
                "pdf_state": state
            },
            f,
            indent=2,
        )
