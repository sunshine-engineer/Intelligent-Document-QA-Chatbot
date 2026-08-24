import tempfile
import unittest
from pathlib import Path

from index_metadata import get_pdf_files, get_pdf_state


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
            pdf.write_bytes(b"first")
            first_state = get_pdf_state(directory)

            pdf.write_bytes(b"second content")

            self.assertNotEqual(first_state, get_pdf_state(directory))


if __name__ == "__main__":
    unittest.main()
