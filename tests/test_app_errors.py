import unittest

from app_errors import ApplicationError, ErrorCategory, user_message
from app_logging import _redact


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


if __name__ == "__main__":
    unittest.main()
