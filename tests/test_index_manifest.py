import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import index_metadata


class FakeVectors:
    def __init__(self, content=b"new"):
        self.content = content

    def save_local(self, directory):
        path = Path(directory)
        (path / "index.faiss").write_bytes(self.content)
        (path / "index.pkl").write_bytes(self.content)

    @property
    def index(self):
        return type("Index", (), {"d": 3})()


class FailingVectors:
    def save_local(self, directory):
        Path(directory, "partial").write_bytes(b"partial")
        raise RuntimeError("simulated save failure")


class IndexManifestTests(unittest.TestCase):
    def _create_artifacts(self, directory):
        index_directory = Path(directory) / "faiss_index"
        index_directory.mkdir()
        (index_directory / "index.faiss").write_bytes(b"faiss-artifact")
        (index_directory / "index.pkl").write_bytes(b"pickle-artifact")
        return index_directory

    def test_manifest_verifies_matching_artifacts_and_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = self._create_artifacts(directory)
            manifest_path = Path(directory) / "vector_store" / "index_manifest.json"

            original_manifest_path = index_metadata.INDEX_MANIFEST_FILE
            index_metadata.INDEX_MANIFEST_FILE = str(manifest_path)
            try:
                manifest = index_metadata.build_index_manifest(
                    index_directory,
                    "ollama",
                    "nomic-embed-text:latest",
                    768,
                )
                index_metadata.save_index_manifest(manifest)

                self.assertTrue(
                    index_metadata.verify_index_manifest(
                        index_directory,
                        "ollama",
                        "nomic-embed-text:latest",
                    )
                )
            finally:
                index_metadata.INDEX_MANIFEST_FILE = original_manifest_path

    def test_manifest_rejects_tampered_artifact(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = self._create_artifacts(directory)
            manifest_path = Path(directory) / "vector_store" / "index_manifest.json"

            original_manifest_path = index_metadata.INDEX_MANIFEST_FILE
            index_metadata.INDEX_MANIFEST_FILE = str(manifest_path)
            try:
                index_metadata.save_index_manifest(
                    index_metadata.build_index_manifest(
                        index_directory, "ollama", "model", 3
                    )
                )
                (index_directory / "index.pkl").write_bytes(b"tampered")

                self.assertFalse(
                    index_metadata.verify_index_manifest(
                        index_directory, "ollama", "model"
                    )
                )
            finally:
                index_metadata.INDEX_MANIFEST_FILE = original_manifest_path

    def test_manifest_rejects_embedding_model_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = self._create_artifacts(directory)
            manifest_path = Path(directory) / "vector_store" / "index_manifest.json"

            original_manifest_path = index_metadata.INDEX_MANIFEST_FILE
            index_metadata.INDEX_MANIFEST_FILE = str(manifest_path)
            try:
                index_metadata.save_index_manifest(
                    index_metadata.build_index_manifest(
                        index_directory, "ollama", "model-a", 3
                    )
                )

                self.assertFalse(
                    index_metadata.verify_index_manifest(
                        index_directory, "ollama", "model-b"
                    )
                )
            finally:
                index_metadata.INDEX_MANIFEST_FILE = original_manifest_path

    def test_atomic_save_replaces_complete_index(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = Path(directory) / "faiss_index"
            index_directory.mkdir()
            (index_directory / "index.faiss").write_bytes(b"old")
            (index_directory / "index.pkl").write_bytes(b"old")

            index_metadata.save_faiss_index_atomically(FakeVectors(), index_directory)

            self.assertEqual((index_directory / "index.faiss").read_bytes(), b"new")
            self.assertEqual((index_directory / "index.pkl").read_bytes(), b"new")

    def test_atomic_save_preserves_previous_index_on_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = Path(directory) / "faiss_index"
            index_directory.mkdir()
            (index_directory / "index.faiss").write_bytes(b"old")
            (index_directory / "index.pkl").write_bytes(b"old")

            with self.assertRaises(RuntimeError):
                index_metadata.save_faiss_index_atomically(
                    FailingVectors(), index_directory
                )

            self.assertEqual((index_directory / "index.faiss").read_bytes(), b"old")

    def test_snapshot_round_trip_and_metadata_write_failure_preserves_previous(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = Path(directory) / "faiss_index"
            manifest = {"documents": {"paper.pdf": {"status": "indexed"}}}
            chunks = [type("Chunk", (), {"metadata": {"source": "paper.pdf"}})()]
            first = index_metadata.save_index_snapshot_atomically(
                FakeVectors(b"old"),
                index_directory,
                "ollama",
                "model",
                manifest,
                chunks,
            )
            self.assertTrue(
                index_metadata.verify_index_snapshot(index_directory, "ollama", "model")
            )
            self.assertEqual(
                index_metadata.load_index_snapshot(index_directory)["metrics"],
                first["metrics"],
            )

            with patch("index_metadata._write_json", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    index_metadata.save_index_snapshot_atomically(
                        FakeVectors(b"new"),
                        index_directory,
                        "ollama",
                        "model",
                        manifest,
                        chunks,
                    )
            self.assertEqual((index_directory / "index.faiss").read_bytes(), b"old")
            self.assertTrue(
                index_metadata.verify_index_snapshot(index_directory, "ollama", "model")
            )
            self.assertEqual((index_directory / "index.pkl").read_bytes(), b"old")

    def test_discard_persisted_index_removes_generated_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            index_directory = Path(directory) / "faiss_index"
            index_directory.mkdir()
            (index_directory / "index.faiss").write_bytes(b"index")
            manifest_path = Path(directory) / "index_manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")

            original_manifest_path = index_metadata.INDEX_MANIFEST_FILE
            index_metadata.INDEX_MANIFEST_FILE = str(manifest_path)
            try:
                index_metadata.discard_persisted_index(index_directory)
                self.assertFalse(index_directory.exists())
                self.assertFalse(manifest_path.exists())
            finally:
                index_metadata.INDEX_MANIFEST_FILE = original_manifest_path


if __name__ == "__main__":
    unittest.main()
