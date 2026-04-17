from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AsgNode(BaseModel):
    id: str
    kind: str
    label: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class AsgEdge(BaseModel):
    id: str
    type: str
    source_id: str
    target_id: str
    confidence: float | None = None
    resolution: str | None = None


class AsgFileArtifact(BaseModel):
    repository_name: str
    repository_url: str
    branch: str
    commit_sha: str
    analysis_timestamp: str
    source_language: str
    relative_path: str
    parser_id: str
    generation_version: str
    dependency_resolution_status: str
    warnings: list[dict[str, object]] = Field(default_factory=list)
    errors: list[dict[str, object]] = Field(default_factory=list)
    nodes: list[AsgNode]
    edges: list[AsgEdge]


class AsgCombinedArtifact(BaseModel):
    repository_name: str
    repository_url: str
    branch: str
    commit_sha: str
    analysis_timestamp: str
    source_language: str
    relative_path: str
    parser_id: str
    generation_version: str
    dependency_resolution_status: str
    warnings: list[dict[str, object]] = Field(default_factory=list)
    errors: list[dict[str, object]] = Field(default_factory=list)
    nodes: list[AsgNode]
    edges: list[AsgEdge]
