import tempfile
import unittest
import os
from pathlib import Path

from index_metadata import (
    compare_document_manifests,
    get_document_manifest,
    get_pdf_files,
    get_pdf_state,
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


if __name__ == "__main__":
    unittest.main()
