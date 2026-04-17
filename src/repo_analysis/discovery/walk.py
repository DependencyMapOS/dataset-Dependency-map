from __future__ import annotations

import fnmatch
from pathlib import Path


def _split_glob_pattern(pattern: str) -> tuple[str, str]:
    """Return (anchor, rest) for simple ** handling."""
    p = pattern.replace("\\", "/")
    if p.startswith("**/"):
        return ("any", p[3:])
    return ("root", p)


def _matches(rel_posix: str, pattern: str) -> bool:
    anchor, rest = _split_glob_pattern(pattern)
    if anchor == "any":
        if "/" in rest:
            prefix, suffix = rest.split("/", 1)
            parts = rel_posix.split("/")
            for i, part in enumerate(parts):
                if fnmatch.fnmatch(part, prefix):
                    sub = "/".join(parts[i + 1 :])
                    return fnmatch.fnmatch(sub, suffix) or fnmatch.fnmatch(sub, suffix.rstrip("/"))
            return False
        return any(fnmatch.fnmatch(part, rest.rstrip("/")) for part in rel_posix.split("/"))
    return fnmatch.fnmatch(rel_posix, rest)


def should_ignore(relative_path: Path, patterns: tuple[str, ...]) -> bool:
    rel = relative_path.as_posix()
    for pat in patterns:
        if _matches(rel, pat):
            return True
    return False


def iter_source_files(
    repo_root: Path,
    *,
    ignore_globs: tuple[str, ...],
) -> list[Path]:
    """Return sorted list of files under repo_root respecting ignore globs."""
    out: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel = path.relative_to(repo_root)
        except ValueError:
            continue
        if ".git" in rel.parts:
            continue
        if should_ignore(rel, ignore_globs):
            continue
        out.append(path)
    return sorted(out)
