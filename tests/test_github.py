"""Tests for the GitHub helpers that need no network."""

from __future__ import annotations

import os
import pathlib
import sys
import unittest
from datetime import date

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from streakkeeper.github import (  # noqa: E402
    Repo,
    _noreply,
    _usable,
    _wanted,
    excluded_repos,
    identity,
    rotated_repos,
)


def repos(count: int) -> list[Repo]:
    return [Repo(f"owner/r{i}", f"https://github.com/owner/r{i}.git") for i in range(count)]


def repo_dict(name: str = "owner/one", **overrides) -> dict:
    base = {"full_name": name, "fork": False, "archived": False, "disabled": False, "size": 10}
    base.update(overrides)
    return base


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
        self.assertTrue(_usable(repo_dict()))

    def test_forks_archived_disabled_and_empty_are_not(self) -> None:
        self.assertFalse(_usable(repo_dict(fork=True)))
        self.assertFalse(_usable(repo_dict(archived=True)))
        self.assertFalse(_usable(repo_dict(disabled=True)))
        self.assertFalse(_usable(repo_dict(size=0)))


class ExclusionTest(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("EXCLUDE_REPOS", None)

    def test_empty_setting_excludes_nothing(self) -> None:
        self.assertEqual(excluded_repos(), set())

    def test_names_are_trimmed_and_lowercased(self) -> None:
        os.environ["EXCLUDE_REPOS"] = " Owner/One , OWNER/Two ,, "
        self.assertEqual(excluded_repos(), {"owner/one", "owner/two"})

    def test_an_excluded_repository_is_not_wanted(self) -> None:
        self.assertTrue(_wanted(repo_dict(), set()))
        self.assertFalse(_wanted(repo_dict(), {"owner/one"}))

    def test_exclusion_is_case_insensitive(self) -> None:
        self.assertFalse(_wanted(repo_dict("Owner/One"), {"owner/one"}))

    def test_a_fork_is_not_wanted_even_when_not_excluded(self) -> None:
        self.assertFalse(_wanted(repo_dict(fork=True), set()))


class IdentityTest(unittest.TestCase):
    def tearDown(self) -> None:
        for name in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL"):
            os.environ.pop(name, None)

    def test_the_noreply_address_is_the_one_github_attributes(self) -> None:
        self.assertEqual(
            _noreply("octocat", 583231),
            "583231+octocat@users.noreply.github.com",
        )

    def test_a_configured_identity_wins_and_needs_no_network(self) -> None:
        os.environ["GIT_AUTHOR_NAME"] = "Someone"
        os.environ["GIT_AUTHOR_EMAIL"] = "someone@example.com"
        self.assertEqual(identity(), ("Someone", "someone@example.com"))


if __name__ == "__main__":
    unittest.main()
