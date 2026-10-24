"""Ask the local open-weight model to write the chosen documentation.

It sees one place at a time: the code, and whatever is already there. It
returns the replacement text only. The script writes it into the file, and a
second model reviews it before anything is committed.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import ollama
from .scan import Candidate

SNIPPET_LINES = 40
MAX_CHARS = 1200


def draft(candidate: Candidate, workdir: Path) -> str:
    """Return the text the local model wrote for this one place."""
    return _parse_text(ollama.chat(_prompt(candidate, workdir)))


def _snippet(workdir: Path, candidate: Candidate) -> str:
    try:
        lines = (workdir / candidate.path).read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return "(unreadable)"
    start = max(candidate.lineno - 1, 0)
    end = min(candidate.end_lineno, start + SNIPPET_LINES)
    return "\n".join(lines[start:end])


def _prompt(candidate: Candidate, workdir: Path) -> str:
    lines = [
        "Write documentation for one place in a Python project.",
        "",
        f"Place: {candidate.kind} {candidate.name} in {candidate.path}",
        f"Reason it needs work: {candidate.reason}",
    ]
    if candidate.current_doc:
        lines.append(f"Current text: {candidate.current_doc}")
    lines.extend(
        [
            "Code:",
            _snippet(workdir, candidate),
            "",
            "Rules:",
            "- Describe what the code does and why it exists, using only the code shown.",
            "- Never invent behaviour you cannot see. No guessing words: likely, probably, suggests, may, might.",
            "- State what it does, not what it could be used for.",
            "- Do not begin with 'This function' or repeat the name; start with what it does.",
            "- Plain prose: no markdown, no backticks, no bullet points, no marketing language.",
            "- At most 3 sentences; for a README section, at most 80 words.",
            "- Return the text only, without quotes or code fences.",
            "",
            'Return JSON only: {"text": "<the documentation>"}',
        ]
    )
    return "\n".join(lines)


def _parse_text(raw: str) -> str:
    """Validate the model's answer before it goes anywhere near a file."""
    try:
        payload = json.loads(raw)
    except ValueError:
        raise RuntimeError(f"local model did not return JSON: {raw[:120]!r}") from None

    if not isinstance(payload, dict):
        raise RuntimeError("local model returned no object")

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("local model returned no text")

    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").split("\n", 1)[-1].strip()

    # A docstring is prose, so markdown never belongs in it.
    cleaned = cleaned.replace("`", "")
    cleaned = " ".join(cleaned.split())

    if len(cleaned) < 10:
        raise RuntimeError(f"local model text is too short: {cleaned!r}")
    if len(cleaned) > MAX_CHARS:
        raise RuntimeError(f"local model text is too long: {len(cleaned)} characters")
    return cleaned