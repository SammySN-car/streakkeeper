"""Tests for the deterministic scan."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.scan import find_candidates  # noqa: E402


def write(root: pathlib.Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class ScanTest(unittest.TestCase):
    def test_fully_documented_file_yields_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(
                root,
                "good.py",
                '"""This module demonstrates a fully documented function."""\n'
                "\n"
                "\n"
                "def documented(x):\n"
                '    """Return x plus one, with enough words to be useful."""\n'
                "    return x + 1\n",
            )
            self.assertEqual(find_candidates(root), [])

    def test_missing_and_thin_docs_are_found_private_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(
                root,
                "bad.py",
                '"""This module has one undocumented function and one thin one."""\n'
                "\n"
                "\n"
                "def missing(x):\n"
                "    return x\n"
                "\n"
                "\n"
                "def thin(x):\n"
                '    """Adds."""\n'
                "    return x + 1\n"
                "\n"
                "\n"
                "def _private(x):\n"
                "    return x\n",
            )
            found = find_candidates(root)
            names = {c.name: c.reason for c in found if c.kind == "function"}
            self.assertEqual(names, {"missing": "missing", "thin": "thin"})

    def test_method_without_docstring_is_a_method_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(
                root,
                "thing.py",
                '"""This module holds a documented class with one method."""\n'
                "\n"
                "\n"
                "class Thing:\n"
                '    """A class with enough explanation to count as useful."""\n'
                "\n"
                "    def method(self):\n"
                "        return 1\n",
            )
            found = find_candidates(root)
            self.assertEqual([(c.kind, c.name) for c in found], [("method", "method")])

    def test_nested_function_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(
                root,
                "nested.py",
                '"""This module holds an outer function with an inner one."""\n'
                "\n"
                "\n"
                "def outer():\n"
                '    """Outer function with a clear explanation of its job."""\n'
                "\n"
                "    def inner():\n"
                "        return 1\n"
                "\n"
                "    return inner\n",
            )
            self.assertEqual(find_candidates(root), [])

    def test_readme_section_that_says_nothing_is_found(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(
                root,
                "README.md",
                "# Demo\n"
                "\n"
                "This project does something useful for somebody, described here.\n"
                "\n"
                "## Install\n"
                "\n"
                "Run it.\n"
                "\n"
                "## Usage\n"
                "\n"
                "This section explains usage in enough detail to be useful.\n",
            )
            found = find_candidates(root)
            self.assertEqual([(c.kind, c.name) for c in found], [("readme-section", "Install")])

    def test_generated_folders_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            write(root, ".venv/bad.py", "def missing(x):\n    return x\n")
            write(root, "node_modules/bad.py", "def missing(x):\n    return x\n")
            self.assertEqual(find_candidates(root), [])


if __name__ == "__main__":
    unittest.main()