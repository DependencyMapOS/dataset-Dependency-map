from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class SourcePosition(BaseModel):
    line: int
    column: int


class SourceSpan(BaseModel):
    start_byte: int
    end_byte: int
    start: SourcePosition
    end: SourcePosition


class AstNode(BaseModel):
    id: str
    kind: str
    label: str = ""
    span: SourceSpan
    text_digest: str | None = None
    children_ids: list[str] = Field(default_factory=list)


class AstEdge(BaseModel):
    id: str
    type: Literal["child", "next_token", "auxiliary"] = "child"
    source_id: str
    target_id: str
    role: str | None = None


class AstFileArtifact(BaseModel):
    """Per-file AST JSON envelope."""

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
    nodes: list[AstNode]
    edges: list[AstEdge]


class AstCombinedArtifact(BaseModel):
    """Repo-level combined AST."""

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
    nodes: list[AstNode]
    edges: list[AstEdge]


def posix_relative_path(path: Path) -> str:
    return path.as_posix().lstrip("./")
