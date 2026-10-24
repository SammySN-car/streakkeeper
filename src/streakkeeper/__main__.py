"""The nightly flow.

gate -> rotate -> clone -> scan -> rank -> write -> review -> verify -> commit
"""

from __future__ import annotations

import argparse
import os
import sys

from . import env, github, rank, review, scan, verify, write

MAX_ATTEMPTS = 3


def run(dry_run: bool = False, force: bool = False) -> int:
    """Run one nightly pass and return a process exit code."""
    if not force and github.contributions_today() > 0:
        print("Already contributed today; nothing to do.")
        return 0

    repos = github.rotated_repos(github.owned_repos(), github.local_now().date())
    if not repos:
        print("No usable repositories found.")
        return 1

    max_repos = int(os.environ.get("MAX_REPOS", "8") or 8)
    for repo in repos[:max_repos]:
        print(f"Looking at {repo.full_name}")
        try:
            workdir = github.clone(repo)
        except RuntimeError as exc:
            print(f"  skipped: {exc}")
            continue

        try:
            candidates = scan.find_candidates(workdir)
            if not candidates:
                print("  nothing to document")
                continue

            shortlist = rank.top_candidates(candidates, workdir, limit=15)
            outcome = _document(repo, workdir, shortlist, dry_run)
            if outcome is not None:
                return outcome
        finally:
            github.discard(workdir)

    print("No documentation written tonight.")
    return 0


def _document(repo, workdir, shortlist, dry_run: bool) -> int | None:
    """Try the best few places until one passes review. None means keep looking."""
    for candidate in shortlist[:MAX_ATTEMPTS]:
        text = write.draft(candidate, workdir)

        approved, reason = review.check(candidate, workdir, text)
        if not approved:
            print(f"  review rejected {candidate.name}: {reason}")
            continue

        target = workdir / candidate.path
        old_source = target.read_text(encoding="utf-8")
        new_source = verify.apply(old_source, candidate, text)

        if candidate.kind != "readme-section" and not verify.code_unchanged(
            old_source, new_source
        ):
            print(f"Refused: the edit would change code in {candidate.path}.")
            return 1

        if dry_run:
            print(f"Would update {repo.full_name}/{candidate.path}:{candidate.lineno}")
            print(f"  reviewed: {reason or 'approved'}")
            print("  --- new text ---")
            for line in text.splitlines():
                print(f"  {line}")
            return 0

        target.write_text(new_source, encoding="utf-8")
        github.commit_and_push(
            workdir,
            candidate.path,
            f"docs: document {candidate.name}",
        )
        print(f"Committed {candidate.path} to {repo.full_name}")
        return 0

    return None


def main(argv: list[str] | None = None) -> int:
    env.load()

    parser = argparse.ArgumentParser(prog="streakkeeper")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change and change nothing",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="ignore today's contribution count; for testing only",
    )
    args = parser.parse_args(argv)
    try:
        return run(dry_run=args.dry_run, force=args.force)
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())