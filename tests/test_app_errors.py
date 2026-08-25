import unittest
import tempfile
from pathlib import Path

from app_errors import ApplicationError, ErrorCategory, user_message
from app_logging import LOGGER, _redact, configure_logging


class ApplicationErrorTests(unittest.TestCase):
    def test_categories_have_safe_retry_message(self):
        message = user_message(ApplicationError(
            ErrorCategory.PROVIDER, "Provider unavailable", retryable=True
        ))
        self.assertIn("Provider error", message)
        self.assertIn("Try again", message)

    def test_unknown_errors_do_not_leak_infrastructure_details(self):
        self.assertNotIn("secret", user_message(RuntimeError("secret")))

    def test_log_redaction_hides_credentials(self):
        self.assertNotIn("secret", _redact("GROQ_API_KEY=secret"))

    def test_log_directory_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            log_directory = Path(directory) / "logs"
            original_handlers = list(LOGGER.handlers)
            try:
                for handler in original_handlers:
                    LOGGER.removeHandler(handler)
                    handler.close()
                configure_logging(log_directory)
                LOGGER.error(
                    "test",
                    extra={"correlation_id": "test-id", "category": "test"},
                )
                self.assertTrue((log_directory / "app.log").exists())
            finally:
                for handler in list(LOGGER.handlers):
                    LOGGER.removeHandler(handler)
                    handler.close()


if __name__ == "__main__":
    unittest.main()
