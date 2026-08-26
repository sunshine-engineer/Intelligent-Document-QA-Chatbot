"""Provider-free integration checks for persistence and retrieval workflows."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import index_metadata
from query_services import ConversationalQueryService, REFUSAL_RESPONSE


class FakeVectors:
    def save_local(self, directory):
        path = Path(directory)
        (path / "index.faiss").write_bytes(b"fake-faiss")
        (path / "index.pkl").write_bytes(b"fake-docstore")


class WorkflowIntegrationTests(unittest.TestCase):
    def test_temporary_index_round_trip_and_fake_provider_retrieval(self):
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
