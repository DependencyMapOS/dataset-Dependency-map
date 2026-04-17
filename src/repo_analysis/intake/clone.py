from __future__ import annotations

import subprocess
from pathlib import Path


def clone_repo(*, url: str, dest: Path, branch: str, shallow: bool = True) -> None:
    """Clone repository into dest (directory must not exist or be empty)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["git", "clone"]
    if shallow:
        cmd += ["--depth", "1", "--branch", branch]
    cmd += [url, str(dest)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git clone failed")


def read_head_commit(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git rev-parse failed")
    return proc.stdout.strip()
