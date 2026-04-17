from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path


def slugify(s: str) -> str:
    s = s.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    return s.strip("-") or "repo"


def run_directory_name(*, repo_name: str, branch: str, commit_sha: str, ts: datetime | None = None) -> str:
    ts = ts or datetime.now(UTC)
    stamp = ts.strftime("%Y%m%dT%H%M%SZ")
    return f"{slugify(repo_name)}/{slugify(branch)}/{commit_sha[:12]}_{stamp}"


def run_root(dataset_root: Path, repo_name: str, branch: str, commit_sha: str) -> Path:
    return dataset_root / run_directory_name(repo_name=repo_name, branch=branch, commit_sha=commit_sha)
