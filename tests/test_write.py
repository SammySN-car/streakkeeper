"""Tests for the local writer's answer, without running a model."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.scan import Candidate  # noqa: E402
from streakkeeper.write import _parse_text, _prompt  # noqa: E402


class ParseTextTest(unittest.TestCase):
    def test_a_valid_answer_is_returned(self) -> None:
        self.assertEqual(_parse_text('{"text": "Return the total."}'), "Return the total.")

    def test_text_is_stripped(self) -> None:
        self.assertEqual(_parse_text('{"text": "  Return the total.  "}'), "Return the total.")

    def test_a_missing_text_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_text('{"other": "value"}')

    def test_empty_text_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_text('{"text": "   "}')

    def test_text_that_is_too_short_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_text('{"text": "Does."}')

    def test_text_that_is_too_long_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_text('{"text": "' + ("word " * 400) + '"}')

    def test_a_non_json_answer_is_refused(self) -> None:
        with self.assertRaises(RuntimeError):
            _parse_text("Here is the documentation you asked for.")

    def test_backticks_and_extra_spaces_are_removed(self) -> None:
        self.assertEqual(
            _parse_text('{"text": "Returns a `Response`   object."}'),
            "Returns a Response object.",
        )
    def test_code_fences_are_stripped(self) -> None:
        self.assertEqual(
            _parse_text('{"text": "```\\nReturn the total.\\n```"}'), "Return the total."
        )


class PromptTest(unittest.TestCase):
    def test_the_prompt_carries_the_place_and_its_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "m.py").write_text("def add(x):\n    return x + 1\n", encoding="utf-8")
            candidate = Candidate("m.py", 1, 2, "function", "add", "missing", None)

            prompt = _prompt(candidate, root)

            self.assertIn("function add in m.py", prompt)
            self.assertIn("return x + 1", prompt)
            self.assertIn('"text"', prompt)


if __name__ == "__main__":
    unittest.main()