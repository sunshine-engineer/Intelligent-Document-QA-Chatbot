"""Verify the repository audit catches missing documentation and broken file links.

File: tests/test_project_consistency.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

import tempfile
import unittest
from pathlib import Path

from scripts.check_project_consistency import check_header, check_links, check_python


class ProjectConsistencyTests(unittest.TestCase):
    """Check rejection paths so audit success cannot hide undocumented scopes."""

    def test_undocumented_nested_function_and_argument_are_rejected(self):
        """Verify private nested callables and undocumented parameters are
        inspected.
        """
        source = '''"""Module purpose."""
def outer(value):
    """Outer purpose without parameter documentation."""
    def inner():
        return value
    return inner()
'''
        errors = check_python(Path("example.py"), source)
        self.assertTrue(any("inner lacks a docstring" in error for error in errors))
        self.assertTrue(any("parameter value" in error for error in errors))

    def test_documented_keyword_and_variadic_parameters_are_accepted(self):
        """Verify documented positional, keyword and variadic names pass
        inspection.
        """
        source = '''"""Module purpose."""
def function(value, *, flag=False, **context):
    """Perform a documented operation.

    Args:
        value: Input item.
        flag: Optional selection flag.
        **context: Additional values.

    Returns:
        The supplied input item.
    """
    return value
'''
        self.assertEqual(check_python(Path("example.py"), source), [])

    def test_invalid_calendar_date_is_rejected_and_json_header_is_exempt(self):
        """Verify format-aware exemptions do not permit invalid text metadata."""
        text = "File: example.py\nMaintainer: sunshine-engineer\nModified: 2026-02-30"
        self.assertTrue(check_header(Path("example.py"), text))
        self.assertEqual(check_header(Path("fixture.json"), "{}\n"), [])

    def test_local_links_are_checked_without_fetching_external_urls(self):
        """Verify missing local targets fail while external URLs are left alone."""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "existing.md").write_text("# Existing\n")
            text = "[ok](existing.md) [bad](missing.md) [remote](https://example.test)"
            errors = check_links(root, Path("README.md"), text)
            self.assertEqual(len(errors), 1)
            self.assertIn("missing.md", errors[0])
