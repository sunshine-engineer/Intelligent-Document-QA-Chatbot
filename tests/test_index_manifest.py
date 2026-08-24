import tempfile
import unittest
from pathlib import Path

import index_metadata


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


if __name__ == "__main__":
    unittest.main()
