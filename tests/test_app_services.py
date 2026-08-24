import unittest
from unittest.mock import Mock, patch

from app_services import IndexConfig, IndexService


class AppServiceTests(unittest.TestCase):
    def test_load_returns_verified_vectors_and_metrics(self):
        vectors = Mock()
        vectors.index.d = 3
        metrics = {
            "schema_version": 1,
            "document_count": 1,
            "chunk_count": 2,
            "per_document_chunk_counts": {"paper.pdf": 2},
            "indexed_at": "2026-01-01T00:00:00+00:00",
        }
        service = IndexService(
            IndexConfig("docs", "index", "ollama", "model"),
            embedding_factory=Mock(),
            loader_factory=Mock(),
            splitter_factory=Mock(),
            faiss_loader=Mock(return_value=vectors),
        )

        with patch("app_services.verify_index_manifest", return_value=True), \
                patch("app_services.load_index_manifest", return_value={"vector_dimension": 3}), \
                patch("app_services.load_metadata", return_value={"metrics": metrics}), \
                patch("app_services.is_valid_index_metrics", return_value=True):
            loaded_vectors, loaded_metrics = service.load()

        self.assertIs(loaded_vectors, vectors)
        self.assertEqual(loaded_metrics, metrics)

    def test_load_rejects_unverified_index(self):
        service = IndexService(
            IndexConfig("docs", "index", "ollama", "model"),
            Mock(), Mock(), Mock(), Mock(),
        )

        with patch("app_services.verify_index_manifest", return_value=False):
            with self.assertRaisesRegex(ValueError, "verification failed"):
                service.load()


if __name__ == "__main__":
    unittest.main()
