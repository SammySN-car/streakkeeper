"""A second model checks the first model's work.

The writer is a small open-weight model running locally. Before anything is
committed, a different model reads the same code and says whether the text is
accurate. It reviews; it never edits, and it never touches a file.

If no reviewer can be reached, the run stops. An unreviewed change is not
committed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

from .scan import Candidate

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_REVIEW_MODEL = "gemini-3.5-flash"
FALLBACK_REVIEW_MODEL = "gemini-3.1-flash-lite"
SNIPPET_LINES = 40
MAX_OUTPUT_TOKENS = 500
RETRYABLE = {429, 500, 502, 503, 504}


def review_model() -> str:
    return (
        os.environ.get("GEMINI_MODEL", DEFAULT_REVIEW_MODEL).strip()
        or DEFAULT_REVIEW_MODEL
    )


def reviewers() -> list[str]:
    """The models to try, in order. One setting overrides the list."""
    configured = os.environ.get("REVIEW_MODELS", "").strip()
    if configured:
        models = [name.strip() for name in configured.split(",") if name.strip()]
        if models:
            return models

    primary = review_model()
    if primary == FALLBACK_REVIEW_MODEL:
        return [primary]
    return [primary, FALLBACK_REVIEW_MODEL]


def check(candidate: Candidate, workdir: Path, text: str) -> tuple[bool, str]:
    """Return whether the text is accurate, and why."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set; the review gate needs it")
    return _parse_review(_ask(_prompt(candidate, workdir, text), key))


def _snippet(workdir: Path, candidate: Candidate) -> str:
    try:
        lines = (workdir / candidate.path).read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return "(unreadable)"
    start = max(candidate.lineno - 1, 0)
    end = min(candidate.end_lineno, start + SNIPPET_LINES)
    return "\n".join(lines[start:end])


def _prompt(candidate: Candidate, workdir: Path, text: str) -> str:
    return "\n".join(
        [
            "You are reviewing documentation before it is committed to a Python project.",
            "Decide whether the proposed text accurately describes the code.",
            "",
            f"Place: {candidate.kind} {candidate.name} in {candidate.path}",
            "Code:",
            _snippet(workdir, candidate),
            "",
            "Current text:",
            candidate.current_doc or "(none)",
            "",
            "Proposed text:",
            text,
            "",
            "Rules:",
            "- Judge only against the code shown.",
            "- Reject text that describes behaviour the code does not have.",
            "- Reject text that is vague enough to be meaningless.",
            "- Reject speculation: words like likely, probably, suggests, may, might, could be used for.",
            "- Reject markdown, backticks or bullet points inside a docstring.",
            "- A missing detail is acceptable; a wrong or hedged statement is not.",
            "",
            'Answer with JSON only: {"ok": true or false, "reason": "<one sentence>"}',
        ]
    )


def _call(model: str, prompt: str, key: str, quiet_thinking: bool) -> dict:
    config = {
        "temperature": 0,
        "responseMimeType": "application/json",
        "maxOutputTokens": MAX_OUTPUT_TOKENS,
    }
    if quiet_thinking:
        config["thinkingConfig"] = {"thinkingBudget": 0}

    body = json.dumps(
        {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": config}
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{GEMINI_URL}/{model}:generateContent",
        data=body,
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        data = json.load(response)
    return json.loads(data["candidates"][0]["content"]["parts"][0]["text"])


def _ask(prompt: str, key: str) -> dict:
    """Try each reviewer once, without letting one busy model end the night."""
    errors: list[str] = []

    for model in reviewers():
        for quiet_thinking in (True, False):
            try:
                return _call(model, prompt, key, quiet_thinking)
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:200]
                errors.append(f"{model}: HTTP {exc.code}")
                if exc.code == 400 and quiet_thinking:
                    # This model does not accept the thinking setting; try plain.
                    continue
                if exc.code in RETRYABLE:
                    break
                raise RuntimeError(f"review API {exc.code}: {detail}") from None
            except (TimeoutError, OSError) as exc:
                errors.append(f"{model}: unreachable ({exc})")
                break
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                errors.append(f"{model}: unusable response ({exc})")
                break

    raise RuntimeError("no reviewer answered: " + "; ".join(errors))


def _parse_review(payload) -> tuple[bool, str]:
    """An unclear verdict counts as a rejection, never as approval."""
    if not isinstance(payload, dict):
        return False, "review response was not an object"

    ok = payload.get("ok")
    if not isinstance(ok, bool):
        return False, "review response had no clear verdict"

    reason = payload.get("reason")
    if not isinstance(reason, str):
        reason = ""
    return ok, reason.strip()[:300]