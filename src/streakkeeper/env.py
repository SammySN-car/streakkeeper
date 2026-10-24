"""Read a local .env file, so keys never have to be typed into a terminal.

Only used for local runs. In GitHub Actions the values arrive as secrets, there
is no .env, and this loader does nothing.

Existing environment variables always win, so a real CI or shell value is never
overwritten by a stale file.
"""

from __future__ import annotations

import os
from pathlib import Path


def load(path: Path | str = ".env") -> int:
    """Load KEY=VALUE pairs from `path`. Returns how many were added."""
    file = Path(path)
    if not file.is_file():
        return 0

    added = 0
    for raw in file.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export ") :].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]

        if key and key not in os.environ:
            os.environ[key] = value
            added += 1
    return added