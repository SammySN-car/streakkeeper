# streakkeeper

Makes one small, real documentation improvement to one of your repositories
every night, so a contribution streak survives the days you are too busy to
commit.

A placeholder commit keeps the streak alive and makes the history worse. This
does the opposite: it finds a docstring or a README section that is missing or
says nothing, writes it properly, proves the code did not change, and commits
that one file.

## What happens each night

1. **Gate.** Ask GitHub how many contributions you have today, in your own
   timezone. If it is more than zero, stop.
2. **Rotate.** Start from a different repository each night, then shallow-clone
   one of them.
3. **Scan.** Walk the Python syntax tree and list the places where
   documentation is missing or too thin: modules, classes, functions, methods,
   and README sections that are a heading and nothing else. This step is
   deterministic and uses no model.
4. **Rank.** A small open-weight model running locally, through Ollama,
   orders those places and keeps the best fifteen.
5. **Write.** The same local model drafts the documentation for the best one.
6. **Review.** A different model reads the code and the draft and says whether
   the text is accurate. Speculation, invented behaviour and markdown are
   rejected.
7. **Verify.** Every docstring is stripped from both versions of the file, and
   the two syntax trees are compared. If anything else differs, the change is
   refused.
8. **Commit.** One file, one commit, one push.

If nothing passes review, nothing is committed. The tool is allowed to do
nothing; it is not allowed to invent work.

## Why two models

The work is done by an open-weight model running on the same machine as the
tool. The hosted model is only an auditor: it never writes, never edits a file,
and never decides what to change. If no reviewer answers, the run stops and the
change is not committed.

That split is deliberate. The part that matters, choosing and writing, stays
open and local. The part that can be a second opinion is allowed to be closed.

## Safety rules

- Documentation only: docstrings, comments and README prose.
- The code must be identical after docstrings are stripped, or the change is
  refused.
- No placeholder commits, no whitespace-only commits, no generated files.
- A run that finds nothing writes nothing.

## Running it

In GitHub Actions, every night at 17:00 UTC:

```yaml
on:
  schedule:
    - cron: "0 17 * * *"
  workflow_dispatch:
```

Two repository secrets are required:

- `GH_PAT` - a personal access token with `repo` scope, because the built-in
  `GITHUB_TOKEN` cannot push to your other repositories.
- `GEMINI_API_KEY` - used by the review gate only.

Locally:

```bash
pip install -e .
cp .env.example .env      # fill in the two keys
python -m streakkeeper --dry-run
```

`--dry-run` prints the text it would write and changes nothing. `--force`
ignores today's contribution count, for testing only.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `GH_PAT` | required | token used to read and push |
| `GEMINI_API_KEY` | required | review gate |
| `GEMINI_MODEL` | `gemini-3.5-flash` | reviewer |
| `REVIEW_MODELS` | primary, then `gemini-3.1-flash-lite` | reviewers to try in order |
| `OLLAMA_MODEL` | `gemma4:e4b` | local open-weight model |
| `STREAK_TIMEZONE` | `Asia/Kolkata` | what "today" means |
| `MAX_REPOS` | `8` | repositories one night may look at |

## Limits

- Python only, for now. The scanner parses Python; other languages are skipped.
- "Too thin" is a character threshold, not a judgment. It is one constant, easy
  to tune after a few real nights.
- GitHub's scheduler can delay or skip a run under load, so the start time
  leaves a buffer before midnight rather than cutting it fine.

## Tests

```bash
python -m unittest discover -s tests
```

59 tests, no network and no model needed.