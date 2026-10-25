"""Everything that talks to GitHub.

- contributions_today(): how many contributions the learner has today.
- owned_repos(): the repositories to rotate through.
- rotated_repos(): which repository to start from tonight.
- clone(): a shallow clone inside the runner's temporary directory.
- commit_and_push(): one commit, one push.

Every call uses GH_PAT, because the built-in GITHUB_TOKEN cannot push to
repositories other than the one running the workflow.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"

CONTRIBUTIONS_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar { totalContributions }
    }
  }
}
"""


@dataclass(frozen=True)
class Repo:
    """One repository the tool may touch."""

    full_name: str
    clone_url: str


def token() -> str:
    """The personal access token, or a clear failure."""
    value = os.environ.get("GH_PAT", "").strip()
    if not value:
        raise RuntimeError("GH_PAT is not set")
    return value


def local_now() -> datetime:
    """The current time where the learner lives."""
    name = os.environ.get("STREAK_TIMEZONE", "Asia/Kolkata").strip() or "Asia/Kolkata"
    try:
        return datetime.now(ZoneInfo(name))
    except Exception:
        # Windows without the tzdata package cannot load the zone database.
        return datetime.now(timezone(timedelta(hours=5, minutes=30)))


def _request(url: str, payload: dict | None = None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
            return (json.loads(raw) if raw else {}), response.headers
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"GitHub API {exc.code} on {url}: {detail}") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API unreachable: {exc.reason}") from None


def login() -> str:
    """Whose contributions we are counting."""
    configured = os.environ.get("GITHUB_LOGIN", "").strip()
    if configured:
        return configured
    data, _ = _request(f"{API}/user")
    return str(data["login"])


def contributions_today() -> int:
    """How many contributions the learner has made today, in their timezone."""
    now = local_now()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    data, _ = _request(
        GRAPHQL,
        {
            "query": CONTRIBUTIONS_QUERY,
            "variables": {
                "login": login(),
                "from": start.isoformat(),
                "to": now.isoformat(),
            },
        },
    )
    if "errors" in data:
        raise RuntimeError(f"GitHub GraphQL: {data['errors']}")
    total = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    return int(total)


def _usable(repo: dict) -> bool:
    """Repositories worth spending tonight on."""
    return (
        not repo.get("fork")
        and not repo.get("archived")
        and not repo.get("disabled")
        and int(repo.get("size", 0)) > 0
    )


def excluded_repos() -> set[str]:
    """Names the learner never wants touched, from EXCLUDE_REPOS."""
    raw = os.environ.get("EXCLUDE_REPOS", "")
    return {name.strip().lower() for name in raw.split(",") if name.strip()}


def _wanted(repo: dict, excluded: set[str]) -> bool:
    """A repository is wanted when it is usable and not on the exclude list."""
    if not _usable(repo):
        return False
    return str(repo.get("full_name", "")).lower() not in excluded


def owned_repos() -> list[Repo]:
    """Repositories the learner owns, excluding forks, archived ones and exclusions."""
    excluded = excluded_repos()
    repos: list[Repo] = []
    page = 1
    while page <= 5:
        data, _ = _request(
            f"{API}/user/repos?affiliation=owner&per_page=100&sort=pushed&page={page}"
        )
        if not isinstance(data, list):
            break
        repos.extend(
            Repo(str(item["full_name"]), str(item["clone_url"]))
            for item in data
            if _wanted(item, excluded)
        )
        if len(data) < 100:
            break
        page += 1
    return repos


def rotated_repos(repos: list[Repo], day) -> list[Repo]:
    """Start from a different repository each night, without storing state."""
    if not repos:
        return []
    offset = day.toordinal() % len(repos)
    return repos[offset:] + repos[:offset]


def _git(args: list[str], cwd: Path | None = None, timeout: int = 300) -> str:
    result = subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout).replace(token(), "***")
        raise RuntimeError(f"git {args[0]} failed: {message.strip()[:400]}")
    return result.stdout


def clone(repo: Repo) -> Path:
    """Shallow-clone one repository into a fresh working directory."""
    target = Path(tempfile.mkdtemp(prefix="streakkeeper-"))
    url = repo.clone_url.replace(
        "https://", f"https://x-access-token:{token()}@", 1
    )
    _git(["clone", "--depth", "1", "--quiet", url, str(target)])
    return target


def discard(workdir: Path) -> None:
    """Remove a working directory, token and all."""
    shutil.rmtree(workdir, ignore_errors=True)


def commit_and_push(workdir: Path, path: str, message: str) -> None:
    """Commit one changed file and push it."""
    name = os.environ.get("GIT_AUTHOR_NAME", "streakkeeper")
    email = os.environ.get("GIT_AUTHOR_EMAIL", "streakkeeper@users.noreply.github.com")

    _git(["config", "user.name", name], cwd=workdir)
    _git(["config", "user.email", email], cwd=workdir)
    _git(["add", "--", path], cwd=workdir)
    _git(["commit", "--no-verify", "-m", message], cwd=workdir)
    _git(["push", "--quiet"], cwd=workdir)