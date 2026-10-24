"""Tests for the GitHub helpers that need no network."""

from __future__ import annotations

import pathlib
import sys
import unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.github import Repo, rotated_repos, _usable  # noqa: E402


def repos(count: int) -> list[Repo]:
    return [Repo(f"owner/r{i}", f"https://github.com/owner/r{i}.git") for i in range(count)]


class RotationTest(unittest.TestCase):
    def test_every_repo_appears_exactly_once(self) -> None:
        items = repos(5)
        result = rotated_repos(items, date(2026, 10, 24))
        self.assertEqual(len(result), 5)
        self.assertEqual(sorted(r.full_name for r in result), sorted(r.full_name for r in items))

    def test_the_starting_repo_changes_with_the_day(self) -> None:
        items = repos(4)
        starts = {
            rotated_repos(items, date(2026, 10, day))[0].full_name
            for day in range(19, 27)
        }
        self.assertGreater(len(starts), 1)

    def test_rotation_is_deterministic(self) -> None:
        items = repos(3)
        day = date(2026, 10, 24)
        self.assertEqual(rotated_repos(items, day), rotated_repos(items, day))

    def test_empty_list_stays_empty(self) -> None:
        self.assertEqual(rotated_repos([], date(2026, 10, 24)), [])


class UsableTest(unittest.TestCase):
    def test_a_normal_repository_is_usable(self) -> None:
        self.assertTrue(_usable({"fork": False, "archived": False, "disabled": False, "size": 120}))

    def test_forks_archived_disabled_and_empty_are_not(self) -> None:
        base = {"fork": False, "archived": False, "disabled": False, "size": 120}
        self.assertFalse(_usable({**base, "fork": True}))
        self.assertFalse(_usable({**base, "archived": True}))
        self.assertFalse(_usable({**base, "disabled": True}))
        self.assertFalse(_usable({**base, "size": 0}))


if __name__ == "__main__":
    unittest.main()