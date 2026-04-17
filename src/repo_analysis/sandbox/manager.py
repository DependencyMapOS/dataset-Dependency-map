from __future__ import annotations

import shutil
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Sandbox:
    path: Path

    def cleanup(self) -> None:
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)


def create_sandbox(parent: Path | None = None) -> Sandbox:
    """Create a fresh directory for one run (never reuse)."""
    base = parent if parent is not None else Path(tempfile.gettempdir())
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"repo_analysis_{uuid.uuid4().hex}"
    path.mkdir(parents=False)
    return Sandbox(path=path)
