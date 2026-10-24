"""Tests for writing a docstring into a file without touching the code."""

from __future__ import annotations

import ast
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.scan import Candidate  # noqa: E402
from streakkeeper.verify import (  # noqa: E402
    apply,
    code_unchanged,
    replace_docstring,
    replace_section,
)


class ReplaceDocstringTest(unittest.TestCase):
    def test_inserts_into_a_function_that_has_none(self) -> None:
        src = "def add(x):\n    return x + 1\n"
        candidate = Candidate("m.py", 1, 2, "function", "add", "missing", None)

        new = replace_docstring(src, candidate, "Return x plus one.")

        self.assertIn('    """Return x plus one."""\n', new)
        self.assertTrue(code_unchanged(src, new))
        self.assertEqual(ast.get_docstring(ast.parse(new).body[0]), "Return x plus one.")
        namespace: dict = {}
        exec(new, namespace)
        self.assertEqual(namespace["add"](2), 3)

    def test_replaces_an_existing_docstring(self) -> None:
        src = 'def add(x):\n    """Old."""\n    return x + 1\n'
        candidate = Candidate("m.py", 1, 3, "function", "add", "thin", "Old.")

        new = replace_docstring(src, candidate, "Return x plus one, clearly.")

        self.assertNotIn('"""Old."""', new)
        self.assertTrue(code_unchanged(src, new))
        self.assertEqual(
            ast.get_docstring(ast.parse(new).body[0]), "Return x plus one, clearly."
        )

    def test_keeps_method_indentation(self) -> None:
        src = (
            "class A:\n"
            '    """Class with enough explanation to be useful."""\n'
            "\n"
            "    def m(self):\n"
            "        return 1\n"
        )
        candidate = Candidate("m.py", 4, 5, "method", "m", "missing", None)

        new = replace_docstring(src, candidate, "Return one.")

        self.assertIn('        """Return one."""\n', new)
        self.assertTrue(code_unchanged(src, new))

    def test_multiline_text_is_indented(self) -> None:
        src = "def f():\n    return 1\n"
        candidate = Candidate("m.py", 1, 2, "function", "f", "missing", None)

        new = replace_docstring(src, candidate, "Return one.\n\nUseful for counting.")

        self.assertTrue(code_unchanged(src, new))
        self.assertEqual(
            ast.get_docstring(ast.parse(new).body[0]),
            "Return one.\n\nUseful for counting.",
        )

    def test_text_containing_triple_quotes_stays_valid(self) -> None:
        src = "def f():\n    return 1\n"
        candidate = Candidate("m.py", 1, 2, "function", "f", "missing", None)

        new = replace_docstring(src, candidate, 'Say """hi""".')

        ast.parse(new)
        self.assertTrue(code_unchanged(src, new))

    def test_module_docstring_is_inserted_before_code(self) -> None:
        src = "x = 1\n"
        candidate = Candidate("m.py", 1, 1, "module", "m", "missing", None)

        new = replace_docstring(src, candidate, "Module docs.")

        self.assertTrue(new.startswith('"""Module docs."""\n'))
        self.assertTrue(code_unchanged(src, new))


class ReplaceSectionTest(unittest.TestCase):
    SOURCE = (
        "# Demo\n"
        "\n"
        "Intro text.\n"
        "\n"
        "## Install\n"
        "\n"
        "Run it.\n"
        "\n"
        "## Usage\n"
        "\n"
        "Usage details here.\n"
    )

    def test_body_is_replaced_and_neighbours_survive(self) -> None:
        candidate = Candidate("README.md", 5, 7, "readme-section", "Install", "thin", "Run it.")
        new = replace_section(self.SOURCE, candidate, "Install with pip.")
        self.assertIn("## Install", new)
        self.assertIn("Install with pip.", new)
        self.assertNotIn("Run it.", new)
        self.assertIn("## Usage", new)
        self.assertIn("Usage details here.", new)

    def test_apply_dispatches_readme_sections(self) -> None:
        candidate = Candidate("README.md", 5, 7, "readme-section", "Install", "thin", "Run it.")
        self.assertEqual(
            apply(self.SOURCE, candidate, "Install with pip."),
            replace_section(self.SOURCE, candidate, "Install with pip."),
        )

    def test_apply_dispatches_python_definitions(self) -> None:
        source = "def f():\n    return 1\n"
        candidate = Candidate("m.py", 1, 2, "function", "f", "missing", None)
        self.assertEqual(
            apply(source, candidate, "Return one."),
            replace_docstring(source, candidate, "Return one."),
        )


if __name__ == "__main__":
    unittest.main()
