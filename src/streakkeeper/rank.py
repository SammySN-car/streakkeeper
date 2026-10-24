"""Ask the local open-weight model to rank the candidates.

The model runs in the same runner, through Ollama, and sees only the locations
the deterministic scan handed over. It reads those parts of the code and
returns an ordering. The top `limit` go on to the writer.

It ranks; it does not write, and it never touches a file.

If the model is unreachable or returns something unusable, the scan order is
kept, so a bad model can slow the run down but cannot break it.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import ollama
from .scan import Candidate

SNIPPET_LINES = 30


def top_candidates(
    candidates: list[Candidate], workdir: Path, limit: int = 15
) -> list[Candidate]:
    """Return at most `limit` candidates, best first."""
    if len(candidates) <= limit:
        return list(candidates)

    prompt = _prompt(candidates, workdir)
    try:
        order = _order_from_response(json.loads(ollama.chat(prompt)), len(candidates))
    except (RuntimeError, ValueError, TypeError):
        order = list(range(len(candidates)))

    return [candidates[i] for i in order[:limit]]


def _snippet(workdir: Path, candidate: Candidate) -> str:
    try:
        lines = (workdir / candidate.path).read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return "(unreadable)"
    start = max(candidate.lineno - 1, 0)
    end = min(candidate.end_lineno, start + SNIPPET_LINES)
    return "\n".join(lines[start:end])


def _prompt(candidates: list[Candidate], workdir: Path) -> str:
    parts = [
        "You rank places in a Python repository where documentation is missing or too thin.",
        "Choose the ones most worth improving first for a reader of this project.",
        "Prefer public, meaningful definitions and README sections readers need.",
        'Return JSON only, shaped like {"order": [index, index, ...]} using the numbers below.',
        "",
    ]
    for index, candidate in enumerate(candidates):
        parts.append(
            f"[{index}] {candidate.kind} {candidate.name} in {candidate.path} "
            f"(lines {candidate.lineno}-{candidate.end_lineno}), reason={candidate.reason}"
        )
        if candidate.current_doc:
            parts.append(f"current text: {candidate.current_doc}")
        parts.append("code:")
        parts.append(_snippet(workdir, candidate))
        parts.append("")
    return "\n".join(parts)


def _order_from_response(payload: dict, count: int) -> list[int]:
    """Validate the model's ordering and append anything it left out."""
    raw = payload.get("order")
    if not isinstance(raw, list):
        raise ValueError("response has no order list")

    order: list[int] = []
    for item in raw:
        if isinstance(item, int) and not isinstance(item, bool) and 0 <= item < count and item not in order:
            order.append(item)
    for index in range(count):
        if index not in order:
            order.append(index)
    return order