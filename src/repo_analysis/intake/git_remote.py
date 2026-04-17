from __future__ import annotations

import subprocess
from urllib.parse import urlparse


def list_remote_branches(url: str) -> list[str]:
    """Return branch names (without refs/heads/ prefix) for a public Git remote."""
    _validate_public_https(url)
    proc = subprocess.run(
        ["git", "ls-remote", "--heads", url],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git ls-remote failed")
    branches: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        ref = parts[1]
        prefix = "refs/heads/"
        if ref.startswith(prefix):
            branches.append(ref[len(prefix) :])
    return sorted(set(branches))


def _validate_public_https(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError("Only http(s) URLs are supported for now.")
    if parsed.hostname in (None, "localhost", "127.0.0.1"):
        raise ValueError("Local remotes are not allowed for public-only mode.")
