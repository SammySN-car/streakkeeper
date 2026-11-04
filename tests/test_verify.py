"""Tests for the one rule that makes unattended commits safe."""

from __future__ import annotations

import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.scan import Candidate  # noqa: E402
from streakkeeper.verify import code_unchanged, replace_docstring  # noqa: E402


class CodeUnchangedTest(unittest.TestCase):
    def test_adding_a_docstring_is_allowed(self) -> None:
        old = "def add(x):\n    return x + 1\n"
        new = 'def add(x):\n    """Return x plus one."""\n    return x + 1\n'
        self.assertTrue(code_unchanged(old, new))

    def test_rewording_a_docstring_is_allowed(self) -> None:
        old = 'def add(x):\n    """Old text."""\n    return x\n'
        new = 'def add(x):\n    """Clearer text."""\n    return x\n'
        self.assertTrue(code_unchanged(old, new))

    def test_comment_only_edits_are_allowed(self) -> None:
        old = "def add(x):\n    return x\n"
        new = "# explained below\ndef add(x):\n    return x  # inline note\n"
        self.assertTrue(code_unchanged(old, new))

    def test_changing_a_literal_is_refused(self) -> None:
        old = "def add(x):\n    return x + 1\n"
        new = 'def add(x):\n    """Return x plus one."""\n    return x + 2\n'
        self.assertFalse(code_unchanged(old, new))

    def test_adding_an_import_is_refused(self) -> None:
        old = "import os\n"
        new = "import os\nimport sys\n"
        self.assertFalse(code_unchanged(old, new))

    def test_removing_a_function_is_refused(self) -> None:
        old = "def a():\n    return 1\n\n\ndef b():\n    return 2\n"
        new = "def a():\n    return 1\n"
        self.assertFalse(code_unchanged(old, new))


class ReplaceDocstringTest(unittest.TestCase):
    """An empty module must not crash the unattended run."""

    def _candidate(self) -> Candidate:
        return Candidate("pkg/__init__.py", 1, 1, "module", "__init__", "missing", None)

    def test_an_empty_module_can_take_a_docstring(self) -> None:
        new = replace_docstring("", self._candidate(), "Package marker.")
        self.assertEqual(new, '"""Package marker."""\n')
        self.assertTrue(code_unchanged("", new))

    def test_comments_survive_when_a_docstring_is_inserted(self) -> None:
        old = "# package marker\n"
        new = replace_docstring(old, self._candidate(), "Package marker.")
        self.assertIn("# package marker", new)
        self.assertTrue(code_unchanged(old, new))


if __name__ == "__main__":
    unittest.main()