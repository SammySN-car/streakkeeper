"""Proof that a documentation change did not alter the program, and the one
place that writes a docstring into a file.

The rule: strip every docstring from both versions, then compare the resulting
syntax trees. Comments are not part of a syntax tree, so a comment-only edit
always passes. A docstring edit passes too, because docstrings are stripped
before the comparison.

If the trees differ, the edit touched code, and the caller must refuse it.
"""

from __future__ import annotations

import ast

_DOC_OWNERS = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
_DEFS = (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)


def _is_docstring(node: ast.stmt) -> bool:
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    )


def _strip_docstrings(tree: ast.AST) -> ast.AST:
    for node in ast.walk(tree):
        if isinstance(node, _DOC_OWNERS):
            body = node.body
            if body and _is_docstring(body[0]):
                node.body = body[1:] or [ast.Pass()]
    return tree


def normalized(source: str) -> str:
    """A dump of the syntax tree with every docstring removed."""
    return ast.dump(_strip_docstrings(ast.parse(source)), include_attributes=False)


def code_unchanged(old_source: str, new_source: str) -> bool:
    """True when the two versions differ only in comments or docstrings."""
    return normalized(old_source) == normalized(new_source)


def _find_node(tree: ast.AST, candidate) -> ast.AST:
    if candidate.kind == "module":
        return tree
    for node in ast.walk(tree):
        if isinstance(node, _DEFS) and node.name == candidate.name and node.lineno == candidate.lineno:
            return node
    raise ValueError(f"no {candidate.kind} named {candidate.name!r} at line {candidate.lineno}")


def _render(text: str, indent: str) -> str:
    """Format the docstring block with the right indentation and quoting."""
    text = text.strip()
    for quote in ('"""', "'''"):
        if quote not in text:
            break
    else:
        text = text.replace('"""', '\\"\\"\\"')
        quote = '"""'

    lines = text.splitlines() or [""]
    if len(lines) == 1:
        return f'{indent}{quote}{lines[0]}{quote}\n'
    body = "".join(f"{indent}{line}\n" if line else "\n" for line in lines)
    return f"{indent}{quote}\n{body}{indent}{quote}\n"


def replace_docstring(old_source: str, candidate, new_text: str) -> str:
    """Return the file's source with the chosen docstring written in.

    Inserts the docstring when the definition has none, replaces it when it
    does, and keeps the surrounding indentation. The caller must still prove
    the result with code_unchanged().
    """
    tree = ast.parse(old_source)
    node = _find_node(tree, candidate)
    lines = old_source.splitlines(keepends=True)

    if candidate.kind == "module":
        indent = ""
    else:
        indent = " " * node.body[0].col_offset

    body = node.body
    doc = body[0] if body and _is_docstring(body[0]) else None
    block = _render(new_text, indent)

    if doc is not None:
        start = doc.lineno - 1
        end = doc.end_lineno
        return "".join(lines[:start] + [block] + lines[end:])

    insert_at = body[0].lineno - 1
    return "".join(lines[:insert_at] + [block] + lines[insert_at:])

def apply(old_source: str, candidate, new_text: str) -> str:
    """Write the text into the right kind of place."""
    if candidate.kind == "readme-section":
        return replace_section(old_source, candidate, new_text)
    return replace_docstring(old_source, candidate, new_text)


def _section_end(lines: list[str], start: int, level: int) -> int:
    """Where a Markdown section stops, ignoring headings inside code fences."""
    in_fence = False
    for index in range(start + 1, len(lines)):
        stripped = lines[index].strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            continue
        if in_fence or not stripped.startswith("#"):
            continue
        if len(stripped) - len(stripped.lstrip("#")) <= level:
            return index
    return len(lines)


def replace_section(old_source: str, candidate, new_text: str) -> str:
    """Replace the body under a Markdown heading, keeping the heading."""
    lines = old_source.splitlines()
    start = candidate.lineno - 1
    level = len(lines[start]) - len(lines[start].lstrip("#"))
    end = _section_end(lines, start, level)

    body = lines[start + 1 : end]
    if any(line.strip().startswith(("```", "~~~")) for line in body):
        raise ValueError("refusing to replace a section that contains a code block")

    block = ["", *[line.rstrip() for line in new_text.strip().splitlines()], ""]
    merged = lines[: start + 1] + block + lines[end:]
    while merged and not merged[-1].strip():
        merged.pop()
    return "\n".join(merged) + "\n"