"""Find places where the documentation could be better.

Deterministic, no model involved. For Python files, walk the syntax tree and
report:

- modules, classes, functions and methods with no docstring
- ones whose docstring is too short to explain anything
- README sections that are a heading followed by almost nothing

Private names, nested functions and generated folders are ignored. Each result
is a Candidate: a file and a location inside it, which is all the local model
needs to go and read that part of the code.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass
from pathlib import Path

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "build",
    "dist",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    "site-packages",
    ".idea",
    ".vscode",
}

# A docstring shorter than this explains too little to be useful.
THIN_DOC_CHARS = 40
# A README section shorter than this is a heading with no substance.
THIN_SECTION_CHARS = 40


@dataclass(frozen=True)
class Candidate:
    """One place that could be documented better."""

    path: str
    lineno: int
    end_lineno: int
    kind: str
    name: str
    reason: str
    current_doc: str | None


def find_candidates(workdir: Path) -> list[Candidate]:
    """Walk one repository and return every documentation gap it can prove."""
    found: list[Candidate] = []
    for path in sorted(_walk(workdir)):
        if path.suffix == ".py":
            found.extend(_python_candidates(workdir, path))
        elif path.name.lower().startswith("readme") and path.suffix.lower() in {".md", ".markdown"}:
            found.extend(_readme_candidates(workdir, path))
    return found


def _walk(workdir: Path):
    for dirpath, dirnames, filenames in os.walk(workdir):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def _reason(doc: str | None) -> str:
    return "missing" if doc is None else "thin"


def _needs_work(doc: str | None) -> bool:
    return doc is None or len(doc.strip()) < THIN_DOC_CHARS


def _python_candidates(workdir: Path, path: Path) -> list[Candidate]:
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (UnicodeDecodeError, SyntaxError, OSError):
        return []

    rel = path.relative_to(workdir).as_posix()
    out: list[Candidate] = []

    module_doc = ast.get_docstring(tree)
    if _needs_work(module_doc):
        out.append(Candidate(rel, 1, 1, "module", path.stem, _reason(module_doc), module_doc))

    for kind, node in _definitions(tree, "module"):
        if node.name.startswith("_"):
            continue
        doc = ast.get_docstring(node)
        if _needs_work(doc):
            out.append(
                Candidate(
                    rel,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    kind,
                    node.name,
                    _reason(doc),
                    doc,
                )
            )
    return out


def _definitions(node: ast.AST, parent: str):
    """Yield (kind, node) for definitions that are worth documenting."""
    for child in ast.iter_child_nodes(node):
        if parent in {"function", "method"} and isinstance(
            child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        if isinstance(child, ast.ClassDef):
            yield "class", child
            yield from _definitions(child, "class")
        elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield ("method" if parent == "class" else "function"), child
            yield from _definitions(child, "function")
        else:
            yield from _definitions(child, parent)


def _readme_candidates(workdir: Path, path: Path) -> list[Candidate]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return []

    rel = path.relative_to(workdir).as_posix()
    headings = [(i, len(line) - len(line.lstrip("#")), line) for i, line in enumerate(lines) if line.lstrip().startswith("#")]
    out: list[Candidate] = []

    for index, (line_no, level, heading) in enumerate(headings):
        end = len(lines)
        for later_no, later_level, _ in headings[index + 1 :]:
            if later_level <= level:
                end = later_no
                break
        body = [line.strip() for line in lines[line_no + 1 : end] if line.strip()]
        text = " ".join(body)
        if len(text) < THIN_SECTION_CHARS:
            name = heading.lstrip("#").strip()
            out.append(
                Candidate(
                    rel,
                    line_no + 1,
                    max(line_no + 1, end),
                    "readme-section",
                    name,
                    _reason(text or None),
                    text or None,
                )
            )
    return out