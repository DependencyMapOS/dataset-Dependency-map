from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException

from repo_analysis.api.deps import settings_dep
from repo_analysis.config import Settings
from repo_analysis.models.manifest_run import DatasetIndex

router = APIRouter(tags=["datasets"])


@router.get("/datasets")
def list_datasets(settings: Settings = Depends(settings_dep)) -> dict[str, object]:
    idx_path = settings.resolved_dataset_root() / "index.json"
    if not idx_path.exists():
        return {"entries": []}
    data = json.loads(idx_path.read_text(encoding="utf-8"))
    idx = DatasetIndex.model_validate(data)
    return {"entries": [e.model_dump() for e in idx.entries]}


@router.get("/datasets/run/{run_path:path}")
def run_metadata(run_path: str, settings: Settings = Depends(settings_dep)) -> dict[str, object]:
    manifest = settings.resolved_dataset_root() / run_path / "metadata" / "run_manifest.json"
    if not manifest.exists():
        raise HTTPException(status_code=404, detail="run not found")
    data: dict[str, object] = json.loads(manifest.read_text(encoding="utf-8"))
    return data
