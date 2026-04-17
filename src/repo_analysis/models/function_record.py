from __future__ import annotations

from pydantic import BaseModel, Field


class SourcePoint(BaseModel):
    line: int
    col: int


class FunctionSpan(BaseModel):
    start: SourcePoint
    end: SourcePoint


class CommentLine(BaseModel):
    line: int
    text: str


class DfgEdgeRecord(BaseModel):
    var_name: str
    def_node_id: str
    use_node_id: str


class CallEdgeRecord(BaseModel):
    callee_id: str
    resolved: bool


class TypeAnnotationRecord(BaseModel):
    node_id: str
    annotation_text: str


class FunctionRecord(BaseModel):
    """Per-function or per-method artifact for extraction and GCB training."""

    id: str
    signature_tokens: list[str] = Field(default_factory=list)
    body_tokens: list[str] = Field(default_factory=list)
    docstring: str | None = None
    comments: list[CommentLine] = Field(default_factory=list)
    span: FunctionSpan
    parent_class: str | None = None
    module_path: str
    language: str
    dfg_edges: list[DfgEdgeRecord] = Field(default_factory=list)
    call_edges: list[CallEdgeRecord] = Field(default_factory=list)
    type_annotations: list[TypeAnnotationRecord] = Field(default_factory=list)
    truncated: bool = False
