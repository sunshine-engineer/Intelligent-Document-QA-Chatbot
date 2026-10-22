"""Regression tests for streamlit app.

File: tests/test_streamlit_app.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from app_runtime import KnowledgeBase
from query_services import ConversationalQueryService

ROOT = Path(__file__).resolve().parents[1]


class StreamlitAppTests(unittest.TestCase):
    """Regression cases for streamlit app."""

    def setUp(self):
        """Create isolated test inputs and register cleanup of environment changes.

        Returns:
            None.
        """
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.env = patch.dict(
            os.environ,
            {
                "PDF_DIRECTORY": self.temporary.name,
                "INDEX_DIRECTORY": self.temporary.name + "/index",
                "GROQ_API_KEY": "",
                "MAX_TOP_K": "10",
                "DEFAULT_TOP_K": "4",
            },
        )
        self.env.start()
        self.addCleanup(self.env.stop)

    def app(self):
        """Create a fresh Streamlit AppTest runner for the repository application.

        Returns:
            Unexecuted AppTest instance with the configured test timeout.
        """
        return AppTest.from_file(str(ROOT / "app.py"), default_timeout=20)

    def test_empty_startup_executes_application_without_providers(self):
        """Verify empty startup executes application without providers."""
        at = self.app().run()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(at.chat_input[0].disabled)
        self.assertIn("text-based PDFs", at.info[0].value)

    def test_invalid_settings_stop_before_constructing_provider(self):
        """Verify invalid settings stop before constructing provider."""
        with (
            patch.dict(os.environ, {"CHUNK_SIZE": "invalid"}),
            patch("app_composition.create_llm") as create,
        ):
            at = self.app().run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Invalid application configuration", at.error[0].value)
        create.assert_not_called()

    def test_discovery_and_manual_refresh_fail_safely(self):
        """Verify discovery and manual refresh fail safely."""
        with patch(
            "app_runtime.get_document_manifest",
            side_effect=PermissionError("private-marker"),
        ):
            at = self.app().run()
            at.button[1].click().run()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(at.chat_input[0].disabled)
        self.assertNotIn("private-marker", at.error[0].value)
        self.assertIn("Refresh Knowledge Base", at.warning[0].value)

    def test_provider_construction_failure_is_safe(self):
        """Verify provider construction failure is safe."""
        with patch(
            "app_composition.create_llm",
            side_effect=ValueError("private-provider-payload"),
        ):
            at = self.app().run()
        self.assertEqual(len(at.exception), 0)
        self.assertNotIn("private-provider-payload", at.error[0].value)

    def test_answer_metadata_survives_rerun_and_stream_failure_does_not_save_turn(self):
        """Verify answer metadata survives rerun and stream failure does not save
        turn.
        """
        chunk = SimpleNamespace(
            page_content="Local evidence", metadata={"source": "paper.pdf", "page": 0}
        )
        kb = KnowledgeBase(
            object(),
            {"document_count": 1, "chunk_count": 1, "indexed_at": "fixture"},
            "v1",
        )
        query = ConversationalQueryService(
            lambda _: [(chunk, 0.9)],
            lambda *_: "Answer [S1]",
            answer_streamer=lambda *_: iter(["Answer ", "[S1]"]),
        )
        with (
            patch("app_composition.create_llm", return_value=object()),
            patch("app_runtime.synchronize_index", return_value=kb),
            patch("app_composition.build_query_service", return_value=query),
        ):
            at = self.app().run()
            at.chat_input[0].set_value("What does the paper say?").run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(len(at.session_state["messages"]), 2)
            at.slider[0].set_value(3).run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(
                at.session_state["messages"][1]["citations"][0]["document"], "paper.pdf"
            )
            self.assertTrue(any("Retrieved Sources" in x.label for x in at.expander))
            self.assertEqual(len(at.get("download_button")), 1)

            def fail(*_):
                """Yield a partial response and then raise a simulated private-
                payload timeout.

                Args:
                    *_: Unused callback arguments accepted to match the service
                        interface.

                Yields:
                    Nonempty response text fragments in provider order.

                Raises:
                    TimeoutError: The fixture reaches the simulated provider
                        failure.
                """
                yield "partial"
                raise TimeoutError("private-stream-payload")

            query.answer_streamer = fail
            at.chat_input[0].set_value("Another question").run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(len(at.session_state["messages"]), 2)
            self.assertNotIn("private-stream-payload", at.error[0].value)

    def test_single_allowed_top_k_is_valid_without_slider_range_error(self):
        """Verify single allowed top k is valid without slider range error."""
        with patch.dict(os.environ, {"MAX_TOP_K": "1", "DEFAULT_TOP_K": "1"}):
            at = self.app().run()
        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.slider), 0)

    def test_configured_question_limit_is_applied_before_query_execution(self):
        """Verify a nondefault UI cap rejects excess input without calling
        providers.
        """
        kb = KnowledgeBase(
            object(),
            {"document_count": 1, "chunk_count": 1, "indexed_at": "fixture"},
            "v1",
        )
        with (
            patch.dict(os.environ, {"MAX_QUESTION_CHARACTERS": "5"}),
            patch("app_composition.create_llm", return_value=object()),
            patch("app_runtime.synchronize_index", return_value=kb),
            patch("app_composition.build_query_service") as query,
        ):
            at = self.app().run()
            at.chat_input[0].set_value("too long").run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("5 characters", at.error[0].value)
        self.assertEqual(at.session_state["messages"], [])
        query.assert_not_called()
