from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RunArtifacts(BaseModel):
    """Paths relative to run root or dataset root as documented."""

    ast_dir: str | None = None
    asg_dir: str | None = None
    functions_jsonl: str | None = None
    gcb_triples_jsonl: str | None = None


class RunManifest(BaseModel):
    run_id: str
    repository_url: str
    repository_name: str
    branch: str
    commit_sha: str
    analysis_timestamp: str
    tool_version: str
    dependency_resolution_status: str
    output_root: str
    duration_seconds: float | None = None
    file_counts_by_language: dict[str, int] = Field(default_factory=dict)
    artifacts: RunArtifacts = Field(default_factory=RunArtifacts)
    artifacts_paths: list[str] = Field(default_factory=list)
    extra: dict[str, Any] = Field(default_factory=dict)


class DatasetIndexEntry(BaseModel):
    run_id: str
    repo: str
    branch: str
    commit: str
    timestamp: str
    path: str


class DatasetIndex(BaseModel):
    entries: list[DatasetIndexEntry] = Field(default_factory=list)
