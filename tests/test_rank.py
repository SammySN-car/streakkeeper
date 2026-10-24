"""Tests for the ranking handoff, without needing a live model."""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.rank import _order_from_response, top_candidates  # noqa: E402
from streakkeeper.scan import Candidate  # noqa: E402


def candidate(index: int) -> Candidate:
    return Candidate(f"file{index}.py", 1, 2, "function", f"f{index}", "missing", None)


class OrderTest(unittest.TestCase):
    def test_valid_order_is_kept(self) -> None:
        self.assertEqual(_order_from_response({"order": [2, 0, 1]}, 3), [2, 0, 1])

    def test_bad_indices_are_dropped(self) -> None:
        self.assertEqual(_order_from_response({"order": [0, 99, -1, "x", 1]}, 2), [0, 1])

    def test_missing_indices_are_appended(self) -> None:
        self.assertEqual(_order_from_response({"order": [1]}, 3), [1, 0, 2])

    def test_duplicates_are_removed(self) -> None:
        self.assertEqual(_order_from_response({"order": [1, 1, 0]}, 2), [1, 0])

    def test_missing_order_list_is_an_error(self) -> None:
        with self.assertRaises(ValueError):
            _order_from_response({}, 3)


class ShortlistTest(unittest.TestCase):
    def test_a_short_list_is_returned_without_calling_the_model(self) -> None:
        items = [candidate(i) for i in range(3)]
        with tempfile.TemporaryDirectory() as tmp:
            result = top_candidates(items, pathlib.Path(tmp), limit=15)
        self.assertEqual(result, items)


if __name__ == "__main__":
    unittest.main()