from __future__ import annotations

from pathlib import Path


def infer_repo_name(repo_root: Path) -> str:
    return repo_root.name or "repo"
