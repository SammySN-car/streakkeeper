"""Tests for the review gate, without calling the API."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.review import (  # noqa: E402
    _parse_review,
    _prompt,
    review_model,
    reviewers,
)
from streakkeeper.scan import Candidate  # noqa: E402


class ParseReviewTest(unittest.TestCase):
    def test_approval_is_returned(self) -> None:
        self.assertEqual(
            _parse_review({"ok": True, "reason": "Accurate."}), (True, "Accurate.")
        )

    def test_rejection_is_returned(self) -> None:
        ok, reason = _parse_review({"ok": False, "reason": "Claims a cache that is not there."})
        self.assertFalse(ok)
        self.assertIn("cache", reason)

    def test_a_missing_verdict_counts_as_rejection(self) -> None:
        ok, _ = _parse_review({"reason": "unsure"})
        self.assertFalse(ok)

    def test_a_non_boolean_verdict_counts_as_rejection(self) -> None:
        ok, _ = _parse_review({"ok": "yes"})
        self.assertFalse(ok)

    def test_a_non_object_counts_as_rejection(self) -> None:
        ok, _ = _parse_review(["ok"])
        self.assertFalse(ok)

    def test_a_missing_reason_is_allowed(self) -> None:
        self.assertEqual(_parse_review({"ok": True}), (True, ""))

    def test_the_default_reviewer_is_a_hosted_model(self) -> None:
        self.assertEqual(review_model(), "gemini-3.5-flash")


class PromptTest(unittest.TestCase):
    def test_the_prompt_contains_code_and_proposed_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "m.py").write_text("def add(x):\n    return x + 1\n", encoding="utf-8")
            candidate = Candidate("m.py", 1, 2, "function", "add", "missing", None)

            prompt = _prompt(candidate, root, "Return x plus one.")

            self.assertIn("return x + 1", prompt)
            self.assertIn("Return x plus one.", prompt)
            self.assertIn("(none)", prompt)


if __name__ == "__main__":
    unittest.main()


class ReviewersTest(unittest.TestCase):
    def tearDown(self) -> None:
        for name in ("REVIEW_MODELS", "GEMINI_MODEL"):
            os.environ.pop(name, None)

    def test_default_is_primary_then_fallback(self) -> None:
        self.assertEqual(reviewers(), ["gemini-3.5-flash", "gemini-3.1-flash-lite"])

    def test_a_configured_list_wins(self) -> None:
        os.environ["REVIEW_MODELS"] = "one-model, two-model"
        self.assertEqual(reviewers(), ["one-model", "two-model"])

    def test_the_primary_is_not_repeated_as_its_own_fallback(self) -> None:
        os.environ["GEMINI_MODEL"] = "gemini-3.1-flash-lite"
        self.assertEqual(reviewers(), ["gemini-3.1-flash-lite"])

if __name__ == "__main__":
    unittest.main()
