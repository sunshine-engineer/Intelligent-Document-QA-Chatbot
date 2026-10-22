"""Verify configurable client, context, UI and logging limits preserve defaults.

File: tests/test_configuration_limits.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document
from langchain_core.runnables import RunnableLambda

from app_composition import build_query_service, create_embedding_factory, create_llm
from app_logging import LOGGER, configure_logging
from scripts import live_provider_smoke
from settings import Settings


class ConfigurationLimitTests(unittest.TestCase):
    """Exercise parsed settings at the actual client and query boundaries."""

    def test_all_adjustable_limits_override_without_exposing_credentials(self):
        """Verify all new settings parse, validate and omit credentials from
        summaries.
        """
        settings = Settings.from_env(
            {
                "GROQ_API_KEY": "synthetic-credential",
                "GROQ_API_BASE_URL": "https://provider.example.test/v1",
                "GROQ_TIMEOUT_SECONDS": "9.5",
                "GROQ_MAX_RETRIES": "0",
                "MAX_OUTPUT_TOKENS": "256",
                "EMBEDDING_TIMEOUT_SECONDS": "12",
                "MAX_QUESTION_CHARACTERS": "80",
                "MAX_HISTORY_MESSAGES": "2",
                "MAX_HISTORY_CHARACTERS": "20",
                "MAX_CONTEXT_CHARACTERS": "40",
                "LOG_DIRECTORY": "custom-logs",
                "LOG_MAX_BYTES": "1024",
                "LOG_BACKUP_COUNT": "0",
            }
        )
        self.assertEqual(settings.validate(), [])
        self.assertEqual(settings.log_directory, Path("custom-logs"))
        self.assertEqual(settings.max_history_messages, 2)
        self.assertEqual(settings.max_question_characters, 80)
        self.assertNotIn("synthetic-credential", str(settings.redacted_summary()))
        llm = create_llm(settings)
        self.assertEqual(llm.request_timeout, 9.5)
        self.assertEqual(llm.max_retries, 0)
        self.assertEqual(llm.max_tokens, 256)
        self.assertEqual(str(llm.groq_api_base), settings.groq_api_base_url)
        self.assertEqual(
            create_embedding_factory(settings)().client_kwargs, {"timeout": 12.0}
        )

    def test_invalid_limits_fail_before_provider_construction(self):
        """Verify nonfinite, nonpositive and malformed limits yield safe errors."""
        for name, value in (
            ("GROQ_TIMEOUT_SECONDS", "nan"),
            ("EMBEDDING_TIMEOUT_SECONDS", "inf"),
            ("MAX_OUTPUT_TOKENS", "0"),
            ("MAX_CONTEXT_CHARACTERS", "-1"),
            ("MAX_HISTORY_MESSAGES", "0"),
            ("GROQ_MAX_RETRIES", "-1"),
            ("LOG_MAX_BYTES", "0"),
            ("LOG_BACKUP_COUNT", "-1"),
            ("MAX_QUESTION_CHARACTERS", "many"),
            ("GROQ_API_BASE_URL", ""),
        ):
            with self.subTest(name=name):
                errors = Settings.from_env({name: value}).validate()
                self.assertTrue(any(name in error for error in errors))

    def test_context_and_rewrite_limits_reach_the_real_chain(self):
        """Verify configured history and evidence budgets constrain model inputs."""
        settings = Settings.from_env(
            {"MAX_CONTEXT_CHARACTERS": "12", "MAX_HISTORY_CHARACTERS": "8"}
        )
        queries = []
        prompts = []
        evidence = [
            Document(page_content="ABCDEFGHIJKL", metadata={"source": "a.pdf"}),
            Document(page_content="MNOPQRSTUVWX", metadata={"source": "b.pdf"}),
        ]

        class Vectors:
            """Supply fixed scored documents and record history-expanded lookup
            text.
            """

            def as_retriever(self, **kwargs):
                """Expose this adapter as the vector store.

                Args:
                    **kwargs: Retriever options accepted for interface
                        compatibility.

                Returns:
                    Namespace exposing this test vector store.
                """
                return SimpleNamespace(vectorstore=self)

            def similarity_search_with_relevance_scores(self, query, k):
                """Record the lookup and return both deterministic evidence
                records.

                Args:
                    query: Actual standalone or history-expanded lookup text.
                    k: Maximum requested evidence count.

                Returns:
                    Two scored documents in descending relevance order.
                """
                queries.append(query)
                return [(document, 0.9) for document in evidence[:k]]

        def answer(prompt):
            """Capture the bounded prompt and return fixed supported text.

            Args:
                prompt: Composed LangChain prompt containing labeled evidence.

            Returns:
                Deterministic answer without an external provider call.
            """
            prompts.append(prompt.to_string())
            return "Supported [S1]."

        service = build_query_service(Vectors(), RunnableLambda(answer), settings, 2)
        service.ask("How does it work?", "discarded-prefix-KEEPTHIS")
        self.assertIn("KEEPTHIS", queries[0])
        self.assertNotIn("discarded-prefix", queries[0])
        self.assertIn("[S1] ABCDEF", prompts[0])
        self.assertIn("[S2] MNOPQR", prompts[0])
        self.assertNotIn("ABCDEFGHIJKL", prompts[0])
        self.assertNotIn("discarded-prefix", prompts[0])

    def test_logging_limits_control_the_rotating_handler(self):
        """Verify supplied file-size and retention settings reach the file handler."""
        original = list(LOGGER.handlers)
        for handler in original:
            LOGGER.removeHandler(handler)
        try:
            with tempfile.TemporaryDirectory() as directory:
                configure_logging(directory, max_bytes=1024, backup_count=1)
                handler = next(h for h in LOGGER.handlers if hasattr(h, "maxBytes"))
                self.assertEqual(handler.maxBytes, 1024)
                self.assertEqual(handler.backupCount, 1)
        finally:
            for handler in list(LOGGER.handlers):
                LOGGER.removeHandler(handler)
                handler.close()
            for handler in original:
                LOGGER.addHandler(handler)

    def test_live_smoke_honors_endpoint_and_timeout_without_network(self):
        """Verify smoke configuration is applied to both mocked provider requests."""
        with (
            patch.dict(
                os.environ,
                {
                    "GROQ_API_KEY": "synthetic-credential",
                    "OLLAMA_SMOKE_URL": "http://embedding.example.test",
                    "GROQ_API_BASE_URL": "https://generation.example.test/v1/",
                    "SMOKE_TIMEOUT_SECONDS": "7",
                },
            ),
            patch.object(
                live_provider_smoke,
                "request_json",
                side_effect=[{"embeddings": [[1.0]]}, {"choices": [{}]}],
            ) as request,
        ):
            live_provider_smoke.main()
        self.assertEqual(request.call_args_list[0].kwargs["timeout"], 7.0)
        self.assertEqual(request.call_args_list[1].kwargs["timeout"], 7.0)
        self.assertEqual(
            request.call_args_list[1].args[0],
            "https://generation.example.test/v1/chat/completions",
        )
