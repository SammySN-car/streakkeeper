"""One small open-weight model, running next to the tool.

Used twice each night: first to rank the documentation gaps, then to write the
one that was chosen. It runs through Ollama on the same machine, so the work
stays local and the model stays open-weight.

Nothing here decides whether a change is allowed. That is the scanner's job and
the reviewer's job.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:11434/api/chat"
DEFAULT_MODEL = "gemma4:e4b"
DEFAULT_TIMEOUT = 600.0


def url() -> str:
    return os.environ.get("OLLAMA_URL", DEFAULT_URL).strip() or DEFAULT_URL


def model_name() -> str:
    return os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL


def timeout() -> float:
    try:
        return float(os.environ.get("OLLAMA_TIMEOUT", DEFAULT_TIMEOUT))
    except ValueError:
        return DEFAULT_TIMEOUT


def chat(prompt: str, json_mode: bool = True) -> str:
    """One question, one answer, no streaming."""
    payload = {
        "model": model_name(),
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": 0},
    }
    if json_mode:
        payload["format"] = "json"

    request = urllib.request.Request(
        url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout()) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"local model HTTP {exc.code}: {detail}") from None
    except TimeoutError:
        raise RuntimeError("local model timed out") from None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"local model unreachable: {exc.reason}") from None

    try:
        return str(data["message"]["content"])
    except (KeyError, TypeError):
        raise RuntimeError("local model returned no message") from None