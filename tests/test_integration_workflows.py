"""Regression tests for integration workflows.

File: tests/test_integration_workflows.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import index_metadata
from query_services import REFUSAL_RESPONSE, ConversationalQueryService


class FakeVectors:
    """Deterministic FAISS-compatible test double for artifact and indexing
    regressions.
    """

    def save_local(self, directory):
        """Write deterministic stand-in FAISS files into the supplied directory.

        Args:
            directory: Temporary directory used to isolate filesystem test
                artifacts.

        Returns:
            None.
        """
        path = Path(directory)
        (path / "index.faiss").write_bytes(b"fake-faiss")
        (path / "index.pkl").write_bytes(b"fake-docstore")


class WorkflowIntegrationTests(unittest.TestCase):
    """Regression cases for integration workflows."""

    def test_temporary_index_round_trip_and_fake_provider_retrieval(self):
        """Verify temporary index round trip and fake provider retrieval."""
        with tempfile.TemporaryDirectory() as directory:
            index_directory = Path(directory) / "index"
            index_metadata.save_faiss_index_atomically(FakeVectors(), index_directory)

            original_manifest = index_metadata.INDEX_MANIFEST_FILE
            index_metadata.INDEX_MANIFEST_FILE = str(
                Path(directory) / "index_manifest.json"
            )
            try:
                index_metadata.save_index_manifest(
                    index_metadata.build_index_manifest(
                        index_directory, "fake", "fake-embedding", 3
                    )
                )
                self.assertTrue(
                    index_metadata.verify_index_manifest(
                        index_directory, "fake", "fake-embedding"
                    )
                )
            finally:
                index_metadata.INDEX_MANIFEST_FILE = original_manifest

            document = SimpleNamespace(
                metadata={"source": "guide.pdf", "page": 1, "chunk_id": "guide-2"},
                page_content="The guide explains reliable retrieval.",
            )
            service = ConversationalQueryService(
                retriever=lambda _: [(document, 0.9)],
                answerer=lambda _, __, evidence: evidence[0].page_content,
            )
            result = service.ask("What does the guide explain?")
            self.assertEqual(result.answer, document.page_content)
            self.assertEqual(result.citations[0].document, "guide.pdf")
            self.assertEqual(result.citations[0].page, 2)

            refusal = ConversationalQueryService(
                retriever=lambda _: [], answerer=lambda *_: "should not run"
            ).ask("Unsupported")
            self.assertEqual(refusal.answer, REFUSAL_RESPONSE)


if __name__ == "__main__":
    unittest.main()
