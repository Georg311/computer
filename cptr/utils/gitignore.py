"""Small .gitignore matcher for fallback file walkers."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

GitignorePattern = tuple[str, bool, bool, bool]


def load_gitignore(root: Path) -> tuple[Path, tuple[GitignorePattern, ...]]:
    """Load the nearest repo/root .gitignore patterns for a search root."""
    base = _ignore_base(root.resolve())
    gitignore = base / ".gitignore"
    if not gitignore.is_file():
        return base, ()

    patterns: list[GitignorePattern] = []
    for raw in gitignore.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("\\#") or line.startswith("\\!"):
            line = line[1:]
        negated = line.startswith("!")
        if negated:
            line = line[1:].strip()
        directory_only = line.endswith("/")
        pattern = line.strip("/")
        if pattern:
            patterns.append((pattern, negated, directory_only, "/" in pattern))
    return base, tuple(patterns)


def is_gitignored(
    path: Path,
    base: Path,
    patterns: tuple[GitignorePattern, ...],
    *,
    is_dir: bool,
) -> bool:
    if not patterns:
        return False
    try:
        rel = path.resolve().relative_to(base).as_posix()
    except ValueError:
        return False

    ignored = False
    name = path.name
    for pattern, negated, directory_only, anchored in patterns:
        if directory_only and not is_dir:
            continue
        if _matches_gitignore_pattern(pattern, rel, name, directory_only, anchored):
            ignored = not negated
    return ignored


def _ignore_base(root: Path) -> Path:
    current = root if root.is_dir() else root.parent
    fallback = current
    for parent in (current, *current.parents):
        if (parent / ".git").exists():
            return parent
        if (parent / ".gitignore").is_file():
            fallback = parent
    return fallback


def _matches_gitignore_pattern(
    pattern: str,
    rel: str,
    name: str,
    directory_only: bool,
    anchored: bool,
) -> bool:
    if anchored:
        return (
            rel == pattern
            or (directory_only and rel.startswith(f"{pattern}/"))
            or fnmatch(rel, pattern)
        )
    return any(fnmatch(part, pattern) for part in rel.split("/")) or fnmatch(name, pattern)
