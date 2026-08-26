import unittest
from pathlib import Path

from settings import Settings, provider_guidance


class SettingsTests(unittest.TestCase):
    def test_defaults_are_stable_and_credentials_are_redacted(self):
        settings = Settings.from_env({})
        self.assertEqual(settings.llm_model, "openai/gpt-oss-20b")
        self.assertEqual(settings.embedding_model, "nomic-embed-text:latest")
        self.assertEqual(settings.pdf_directory, Path("research_papers"))
        self.assertEqual(settings.default_top_k, 4)
        self.assertEqual(settings.missing_credentials, ["GROQ_API_KEY"])
        self.assertNotIn("groq_api_key", settings.redacted_summary())

    def test_environment_overrides_are_applied(self):
        settings = Settings.from_env(
            {
                "GROQ_API_KEY": "secret-value",
                "LLM_MODEL": "model-a",
                "EMBEDDING_MODEL": "embed-a",
                "OLLAMA_HOST": "http://localhost:11434",
                "PDF_DIRECTORY": "docs",
                "INDEX_DIRECTORY": "index",
                "CHUNK_SIZE": "800",
                "CHUNK_OVERLAP": "100",
                "DEFAULT_TOP_K": "3",
                "MAX_TOP_K": "6",
            }
        )
        self.assertEqual(settings.llm_model, "model-a")
        self.assertEqual(settings.embedding_model, "embed-a")
        self.assertEqual(settings.chunk_size, 800)
        self.assertEqual(settings.index_directory, Path("index"))
        self.assertEqual(settings.validate(), [])

    def test_invalid_chunk_and_retrieval_settings_are_reported(self):
        settings = Settings.from_env(
            {
                "CHUNK_SIZE": "100",
                "CHUNK_OVERLAP": "100",
                "DEFAULT_TOP_K": "8",
                "MAX_TOP_K": "4",
                "RETRIEVAL_RELEVANCE_THRESHOLD": "2",
            }
        )
        errors = settings.validate()
        self.assertTrue(any("CHUNK_OVERLAP" in error for error in errors))
        self.assertTrue(any("DEFAULT_TOP_K" in error for error in errors))
        self.assertTrue(any("RELEVANCE_THRESHOLD" in error for error in errors))

    def test_malformed_numeric_values_are_safe_validation_errors(self):
        settings = Settings.from_env(
            {"CHUNK_SIZE": "large", "RETRIEVAL_RELEVANCE_THRESHOLD": "high"}
        )
        self.assertIn("CHUNK_SIZE must be an integer.", settings.validate())
        self.assertIn(
            "RETRIEVAL_RELEVANCE_THRESHOLD must be a number.", settings.validate()
        )

    def test_provider_guidance_is_specific_and_does_not_echo_payload(self):
        self.assertIn(
            "authentication", provider_guidance(Exception("401 secret-token")).lower()
        )
        self.assertIn(
            "model", provider_guidance(Exception("404 model missing")).lower()
        )
        self.assertNotIn(
            "secret-token", provider_guidance(Exception("401 secret-token"))
        )


if __name__ == "__main__":
    unittest.main()
