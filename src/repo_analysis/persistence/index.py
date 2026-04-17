from __future__ import annotations

import json
from pathlib import Path

from repo_analysis.models.manifest_run import DatasetIndex, DatasetIndexEntry
from repo_analysis.persistence.writer import atomic_write_json


def append_index(dataset_root: Path, entry: DatasetIndexEntry) -> None:
    path = dataset_root / "index.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        idx = DatasetIndex.model_validate(data)
    else:
        idx = DatasetIndex()
    idx.entries.append(entry)
    atomic_write_json(path, idx.model_dump())
