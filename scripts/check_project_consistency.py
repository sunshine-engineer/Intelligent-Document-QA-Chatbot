"""Check documented source contracts and file coverage without importing the app.

File: scripts/check_project_consistency.py
Maintainer: sunshine-engineer
Modified: 2026-10-23
"""

from __future__ import annotations

import ast
import datetime
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY_SUFFIXES = {".pdf", ".png"}
HEADER_EXEMPTIONS = {"LICENSE", "uv.lock"}


def project_files(root: Path) -> list[Path]:
    """Enumerate tracked and unignored project-file candidates.

    Args:
        root: Repository checkout containing Git metadata.

    Returns:
        Sorted relative candidates; main() filters deleted files. Ignored local
        state is excluded by Git.

    Raises:
        subprocess.CalledProcessError: Git cannot inspect the checkout.
    """
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return sorted(
        {Path(name.decode()) for name in result.stdout.split(b"\0") if name},
        key=lambda path: path.as_posix(),
    )


def check_python(path: Path, source: str) -> list[str]:
    """Check module metadata and callable documentation without executing code.

    Args:
        path: Repository-relative Python module path.
        source: UTF-8 module source to inspect.

    Returns:
        Missing-docstring or undocumented-parameter diagnostic strings.

    Raises:
        SyntaxError: Source is not syntactically valid Python.
    """
    errors = []
    tree = ast.parse(source)
    if not ast.get_docstring(tree):
        errors.append(f"{path}: missing module docstring")
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        doc = ast.get_docstring(node)
        if not doc:
            errors.append(f"{path}:{node.lineno}: {node.name} lacks a docstring")
            continue
        if isinstance(node, ast.ClassDef):
            continue
        parameters = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        parameters += [arg for arg in (node.args.vararg, node.args.kwarg) if arg]
        for argument in parameters:
            if argument.arg in ("self", "cls"):
                continue
            if not re.search(rf"(?m)^\s*\*{{0,2}}{argument.arg}:\s", doc):
                errors.append(
                    f"{path}:{node.lineno}: {node.name} does not document "
                    f"parameter {argument.arg}"
                )
    return errors


def check_header(path: Path, text: str) -> list[str]:
    """Require format-compatible metadata without guessing authorship.

    Args:
        path: Repository-relative text-file path.
        text: Decoded file content; only the initial header region is inspected.

    Returns:
        Header diagnostics; JSON, generated lock and license text are exempt.
    """
    if path.name in HEADER_EXEMPTIONS or path.suffix == ".json":
        return []
    head = text[:1200]
    errors = []
    for required in (f"File: {path.as_posix()}", "Maintainer:", "Modified:"):
        if required not in head:
            errors.append(f"{path}: missing header field {required}")
    date = re.search(r"Modified:\s*(\d{4}-\d{2}-\d{2})", head)
    try:
        if date is None:
            raise ValueError("missing ISO date")
        datetime.date.fromisoformat(date.group(1))
    except ValueError:
        errors.append(f"{path}: invalid modified date")
    return errors


def check_links(root: Path, path: Path, source: str) -> list[str]:
    """Verify local Markdown file targets without contacting external websites.

    Args:
        root: Repository directory used to resolve paths.
        path: Markdown source path relative to root.
        source: Markdown text; external URLs and in-page anchors are ignored.

    Returns:
        Diagnostics for broken local file targets. Anchor existence is not
        checked.
    """
    errors = []
    for target in re.findall(r"\[[^\]]*\]\(([^\s)]+)\)", source):
        if "://" in target or target.startswith(("#", "mailto:")):
            continue
        destination = root / path.parent / target.split("#", 1)[0]
        if not destination.exists():
            errors.append(f"{path}: broken local link {target}")
    return errors


def main() -> int:
    """Audit source docs, supported format parsing, links and complete file
    inventory.

    Returns:
        Zero when checks pass; one after printing actionable diagnostics on
        failure.

    Raises:
        OSError: A project file cannot be read.
        subprocess.CalledProcessError: Git cannot enumerate the checkout.
    """
    errors = []
    files = [path for path in project_files(ROOT) if (ROOT / path).is_file()]
    inventory = (ROOT / "docs/file-inventory.md").read_text(encoding="utf-8")
    python_count = 0
    for path in files:
        if f"| `{path.as_posix()}` |" not in inventory:
            errors.append(f"{path}: missing from docs/file-inventory.md")
        if path.suffix in BINARY_SUFFIXES:
            continue
        source = (ROOT / path).read_bytes().decode("utf-8")
        errors.extend(check_header(path, source))
        if not source.endswith("\n") or "\r" in source:
            errors.append(f"{path}: require LF text with a final newline")
        try:
            if path.suffix == ".py":
                python_count += 1
                errors.extend(check_python(path, source))
            elif path.suffix == ".json":
                json.loads(source)
            elif path.suffix in (".toml", ".lock"):
                tomllib.loads(source)
        except (SyntaxError, ValueError) as error:
            errors.append(f"{path}: invalid syntax: {error}")
        if path.suffix == ".md":
            errors.extend(check_links(ROOT, path, source))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Consistency checks passed: {len(files)} files, {python_count} Python modules."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
