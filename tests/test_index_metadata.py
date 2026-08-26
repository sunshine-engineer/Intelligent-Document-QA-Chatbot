import tempfile
import unittest
import os
from pathlib import Path

from index_metadata import (
    build_index_metrics,
    compare_document_manifests,
    get_document_manifest,
    get_pdf_files,
    get_pdf_state,
)


class FakeDocstore:
    def __init__(self, documents):
        self.documents = documents

    def search(self, document_id):
        return self.documents.get(document_id)


class FakeVectors:
    index_to_docstore_id = {"0": "chunk-a", "1": "chunk-a-2", "2": "chunk-b"}
    docstore = FakeDocstore(
        {
            "chunk-a": type("Document", (), {"metadata": {"source": "a.pdf"}})(),
            "chunk-a-2": type("Document", (), {"metadata": {"source": "a.pdf"}})(),
            "chunk-b": type("Document", (), {"metadata": {"source": "b.pdf"}})(),
        }
    )


class PdfStateTests(unittest.TestCase):
    def test_missing_directory_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "research_papers"

            self.assertEqual(get_pdf_files(str(missing)), [])
            self.assertIsInstance(get_pdf_state(str(missing)), str)

    def test_empty_directory_is_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(get_pdf_files(directory), [])

    def test_pdf_filter_is_case_insensitive_and_sorted(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "z.PDF").write_bytes(b"z")
            Path(directory, "a.pdf").write_bytes(b"a")
            Path(directory, "notes.txt").write_text("ignore", encoding="utf-8")

            self.assertEqual(get_pdf_files(directory), ["a.pdf", "z.PDF"])

    def test_pdf_state_changes_when_file_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory, "paper.pdf")
            pdf.write_bytes(b"one")
            first_state = get_pdf_state(directory)

            pdf.write_bytes(b"two")

            self.assertNotEqual(first_state, get_pdf_state(directory))

    def test_touching_unchanged_pdf_does_not_change_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory, "paper.pdf")
            pdf.write_bytes(b"same content")
            first_manifest = get_document_manifest(directory)

            os.utime(pdf, None)

            self.assertEqual(first_manifest, get_document_manifest(directory))

    def test_document_changes_classify_added_changed_unchanged_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf_a = Path(directory, "a.pdf")
            pdf_b = Path(directory, "b.pdf")
            pdf_a.write_bytes(b"old")
            pdf_b.write_bytes(b"same")
            previous = get_document_manifest(directory)

            pdf_a.write_bytes(b"new")
            pdf_b.unlink()
            Path(directory, "c.pdf").write_bytes(b"added")
            current = get_document_manifest(directory)

            self.assertEqual(
                compare_document_manifests(previous, current),
                {
                    "added": ["c.pdf"],
                    "changed": ["a.pdf"],
                    "unchanged": [],
                    "removed": ["b.pdf"],
                },
            )

    def test_metrics_persist_document_and_chunk_counts(self):
        metrics = build_index_metrics(
            FakeVectors(),
            {"documents": {"a.pdf": {}, "b.pdf": {}}},
        )

        self.assertEqual(metrics["document_count"], 2)
        self.assertEqual(metrics["chunk_count"], 3)
        self.assertEqual(
            metrics["per_document_chunk_counts"],
            {"a.pdf": 2, "b.pdf": 1},
        )


if __name__ == "__main__":
    unittest.main()
