import unittest
from types import SimpleNamespace
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

        with (
            patch("app_services.verify_index_manifest", return_value=True),
            patch(
                "app_services.load_index_snapshot",
                return_value={"vector_dimension": 3, "metrics": metrics},
            ),
            patch("app_services.is_valid_index_metrics", return_value=True),
        ):
            loaded_vectors, loaded_metrics = service.load()

        self.assertIs(loaded_vectors, vectors)
        self.assertEqual(loaded_metrics, metrics)

    def test_load_rejects_unverified_index(self):
        service = IndexService(
            IndexConfig("docs", "index", "ollama", "model"),
            Mock(),
            Mock(),
            Mock(),
            Mock(),
        )

        with patch("app_services.verify_index_manifest", return_value=False):
            with self.assertRaisesRegex(ValueError, "verification failed"):
                service.load()

    def test_incremental_changes_without_verified_vectors_use_full_rebuild(self):
        document = SimpleNamespace(
            metadata={"source": "docs/paper.pdf"}, page_content="content"
        )
        loader = Mock()
        loader.load.return_value = [document]
        splitter = Mock()
        splitter.split_documents.return_value = [document]
        vectors = Mock()
        vectors.index.d = 3
        service = IndexService(
            IndexConfig("docs", "index", "ollama", "model"),
            embedding_factory=Mock(return_value="embeddings"),
            loader_factory=Mock(return_value=loader),
            splitter_factory=Mock(return_value=splitter),
            faiss_loader=Mock(),
            faiss_factory=Mock(return_value=vectors),
        )
        changes = {
            "added": ["paper.pdf"],
            "changed": [],
            "removed": [],
            "unchanged": [],
        }

        with (
            patch(
                "app_services.get_document_manifest",
                return_value={"documents": {"paper.pdf": {}}},
            ),
            patch(
                "app_services.save_index_snapshot_atomically",
                return_value={"metrics": {"document_count": 1, "chunk_count": 1}},
            ),
        ):
            built_vectors, _, _, chunks = service.build(changes, None)

        service.faiss_factory.assert_called_once_with([document], "embeddings")
        self.assertIs(built_vectors, vectors)
        self.assertEqual(chunks, [document])


if __name__ == "__main__":
    unittest.main()
