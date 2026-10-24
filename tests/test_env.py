"""Tests for reading a local .env without touching real secrets."""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.env import load  # noqa: E402

KEYS = ["SK_TEST_ONE", "SK_TEST_TWO", "SK_TEST_THREE", "SK_TEST_KEEP", "SK_TEST_EXPORT"]


class LoadTest(unittest.TestCase):
    def tearDown(self) -> None:
        for key in KEYS:
            os.environ.pop(key, None)

    def write(self, text: str) -> pathlib.Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        self.addCleanup(pathlib.Path(tmp.name).unlink, missing_ok=True)
        return pathlib.Path(tmp.name)

    def test_values_are_read_and_quotes_removed(self) -> None:
        path = self.write('SK_TEST_ONE=abc\nSK_TEST_TWO="quoted value"\nSK_TEST_THREE=123\n')
        self.assertEqual(load(path), 3)
        self.assertEqual(os.environ["SK_TEST_ONE"], "abc")
        self.assertEqual(os.environ["SK_TEST_TWO"], "quoted value")
        self.assertEqual(os.environ["SK_TEST_THREE"], "123")

    def test_comments_and_blank_lines_are_ignored(self) -> None:
        path = self.write("# a comment\n\n   \nnot a pair\nSK_TEST_ONE=value\n")
        self.assertEqual(load(path), 1)
        self.assertEqual(os.environ["SK_TEST_ONE"], "value")

    def test_existing_environment_wins(self) -> None:
        os.environ["SK_TEST_KEEP"] = "from-shell"
        path = self.write("SK_TEST_KEEP=from-file\n")
        self.assertEqual(load(path), 0)
        self.assertEqual(os.environ["SK_TEST_KEEP"], "from-shell")

    def test_export_prefix_is_allowed(self) -> None:
        path = self.write("export SK_TEST_EXPORT=value\n")
        self.assertEqual(load(path), 1)
        self.assertEqual(os.environ["SK_TEST_EXPORT"], "value")

    def test_a_missing_file_is_not_an_error(self) -> None:
        self.assertEqual(load(pathlib.Path(tempfile.gettempdir()) / "no-such-file.env"), 0)


if __name__ == "__main__":
    unittest.main()