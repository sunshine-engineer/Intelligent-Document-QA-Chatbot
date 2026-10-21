"""Regressions for issues reproduced by the portfolio readiness review."""

import copy
import io
import json
import logging
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app_logging import LOGGER, log_exception
from app_runtime import synchronize_index
from app_services import IndexConfig, IndexService
from evaluation.run_offline import evaluate, load_dataset
from index_metadata import (
    build_index_snapshot,
    document_state,
    get_document_manifest,
    get_pdf_state,
    save_index_snapshot_atomically,
)


class FakeVectors:
    index = SimpleNamespace(d=3)

    def save_local(self, directory):
        for name in ("index.faiss", "index.pkl"):
            Path(directory, name).write_bytes(b"fixture")


class IndexLifecycleRegressions(unittest.TestCase):
    def test_processing_status_does_not_change_document_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "paper.pdf").write_bytes(b"pdf fixture")
            manifest = get_document_manifest(directory)
            manifest["documents"]["paper.pdf"]["status"] = "indexed"
            self.assertEqual(document_state(manifest), get_pdf_state(directory))

    def test_unchanged_startup_rerun_restart_and_configuration_change(self):
        with tempfile.TemporaryDirectory() as directory:
            pdfs = Path(directory, "pdfs")
            pdfs.mkdir()
            Path(pdfs, "paper.pdf").write_bytes(b"pdf fixture")
            config = IndexConfig(str(pdfs), str(Path(directory, "index")), "test", "v1")
            chunk = SimpleNamespace(
                page_content="evidence", metadata={"source": "paper.pdf"}
            )
            loader = Mock()
            loader.load.return_value = [chunk]
            splitter = Mock()
            splitter.split_documents.return_value = [chunk]
            embeddings = Mock(return_value="embedding model")
            factory = Mock(return_value=FakeVectors())
            load = Mock(return_value=FakeVectors())
            service = IndexService(
                config,
                embeddings,
                Mock(return_value=loader),
                Mock(return_value=splitter),
                load,
                factory,
            )
            first = synchronize_index(service)
            for _ in range(3):
                self.assertIs(synchronize_index(service, first), first)
            self.assertEqual(factory.call_count, 1)
            load.assert_not_called()
            restarted = synchronize_index(service)
            self.assertIsNotNone(restarted.vectors)
            self.assertEqual(factory.call_count, 1)
            load.assert_called_once()
            changed = IndexConfig(
                str(pdfs), config.index_directory, "test", "v1", 500, 50
            )
            service.config = changed
            with self.assertRaisesRegex(ValueError, "chunk configuration"):
                service.load()
            synchronize_index(service, restarted)
            self.assertEqual(factory.call_count, 2)
            Path(pdfs, "paper.pdf").unlink()
            self.assertIsNone(synchronize_index(service).vectors)
            self.assertFalse(Path(config.index_directory).exists())

    def test_legacy_snapshot_rebuilds_with_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            vectors = FakeVectors()
            snapshot = save_index_snapshot_atomically(
                vectors, directory, "test", "v1", {"documents": {}}, []
            )
            self.assertIsNone(snapshot["indexing_config"])

    def test_discovery_failure_propagates_to_safe_ui_boundary(self):
        service = Mock()
        with patch("app_runtime.get_document_manifest", side_effect=PermissionError):
            with self.assertRaises(PermissionError):
                synchronize_index(service)

    def test_empty_text_does_not_replace_previous_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            service = IndexService(
                IndexConfig(directory, str(Path(directory, "index")), "test", "v1"),
                Mock(),
                Mock(),
                Mock(),
                Mock(),
                Mock(),
            )
            service.loader_factory.return_value.load.return_value = []
            service.splitter_factory.return_value.split_documents.return_value = []
            with self.assertRaisesRegex(ValueError, "No extractable text"):
                service.build()
            service.faiss_factory.assert_not_called()

    def test_snapshot_hash_agrees_with_discovery(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "paper.pdf").write_bytes(b"fixture")
            for name in ("index.faiss", "index.pkl"):
                Path(directory, name).write_bytes(b"artifact")
            manifest = get_document_manifest(directory)
            manifest["documents"]["paper.pdf"]["status"] = "indexed"
            snapshot = build_index_snapshot(directory, "test", "v1", 3, manifest, [])
            self.assertEqual(snapshot["pdf_state"], get_pdf_state(directory))


class LoggingRegressions(unittest.TestCase):
    def test_emitted_chained_exception_contains_neither_secret_nor_payload(self):
        output = io.StringIO()
        handler = logging.StreamHandler(output)
        LOGGER.addHandler(handler)
        try:
            try:
                try:
                    raise ValueError("GROQ_API_KEY=fake-secret private-document-marker")
                except ValueError as cause:
                    raise RuntimeError(
                        "serialized prompt private-prompt-marker"
                    ) from cause
            except RuntimeError as error:
                log_exception("test-reference", "provider", error)
        finally:
            LOGGER.removeHandler(handler)
        text = output.getvalue()
        self.assertIn("RuntimeError", text)
        for marker in (
            "fake-secret",
            "private-document-marker",
            "private-prompt-marker",
        ):
            self.assertNotIn(marker, text)


class EvaluationRegressions(unittest.TestCase):
    def setUp(self):
        self.dataset = load_dataset(Path("evaluation/dataset.v2.json"))

    def test_partial_source_recall_is_fractional(self):
        self.dataset["cases"] = [
            {
                "id": "multi-source",
                "question": "attention context",
                "expected_sources": ["attention.pdf", "llm.pdf"],
                "expected_pages": [1, 3],
                "answerable": True,
            }
        ]
        self.dataset["documents"] = self.dataset["documents"][:1]
        self.assertEqual(evaluate(self.dataset)["recall_at_k"], 0.5)

    def test_citation_page_must_belong_to_expected_document(self):
        self.dataset["cases"] = [
            {
                "id": "crossed-pages",
                "question": "attention context",
                "expected_sources": ["attention.pdf", "llm.pdf"],
                "expected_pages": [3, 1],
                "answerable": True,
            }
        ]
        self.assertEqual(evaluate(self.dataset)["citation_correctness"], 0)

    def test_clarification_does_not_reduce_retrieval_mrr(self):
        result = evaluate(self.dataset)
        self.assertEqual(result["retrieval_case_count"], 3)
        self.assertEqual(result["clarification_case_count"], 1)
        self.assertEqual(result["mrr"], 1)

    def test_cli_returns_failure_and_still_writes_degraded_results(self):
        bad = copy.deepcopy(self.dataset)
        bad["cases"][0]["expected_sources"] = ["missing.pdf"]
        with tempfile.TemporaryDirectory() as directory:
            dataset = Path(directory, "dataset.json")
            output = Path(directory, "results.json")
            dataset.write_text(json.dumps(bad))
            process = subprocess.run(
                [
                    sys.executable,
                    "evaluation/run_offline.py",
                    "--dataset",
                    str(dataset),
                    "--output",
                    str(output),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 1)
            self.assertTrue(output.is_file())
            self.assertIn("thresholds failed", process.stderr)
