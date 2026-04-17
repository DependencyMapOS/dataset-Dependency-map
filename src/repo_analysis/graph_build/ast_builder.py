from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from tree_sitter import Node

from repo_analysis.models.ast import AstEdge, AstNode, SourcePosition, SourceSpan


@dataclass
class AstBuildResult:
    nodes: list[AstNode]
    edges: list[AstEdge]


def _line_col(node: Node) -> tuple[SourcePosition, SourcePosition]:
    start = SourcePosition(line=int(node.start_point.row) + 1, column=int(node.start_point.column))
    end = SourcePosition(line=int(node.end_point.row) + 1, column=int(node.end_point.column))
    return start, end


def build_ast_for_tree(
    *,
    commit_sha: str,
    relative_path: str,
    root: Node,
    source: bytes,
) -> AstBuildResult:
    """Build per-file AST from a tree-sitter root node."""
    collision: dict[tuple[str, int, int, str], int] = defaultdict(int)
    nodes: list[AstNode] = []
    edges: list[AstEdge] = []

    def node_id(n: Node) -> str:
        key = (relative_path, n.start_byte, n.end_byte, n.type)
        idx = collision[key]
        collision[key] += 1
        suffix = "" if idx == 0 else f":{idx - 1}"
        return f"ast:{commit_sha}:{relative_path}:{n.start_byte}:{n.end_byte}:{n.type}{suffix}"

    def walk(n: Node, parent_id: str | None) -> str:
        nid = node_id(n)
        child_ids: list[str] = []
        for ch in n.named_children:
            child_ids.append(walk(ch, nid))
        start, end = _line_col(n)
        span = SourceSpan(
            start_byte=n.start_byte,
            end_byte=n.end_byte,
            start=start,
            end=end,
        )
        label = source[n.start_byte : n.end_byte].decode("utf-8", errors="replace")[:200]
        nodes.append(
            AstNode(
                id=nid,
                kind=n.type,
                label=label,
                span=span,
                children_ids=child_ids,
            )
        )
        if parent_id is not None:
            eid = f"ast:{commit_sha}:{relative_path}:edge:{parent_id}->{nid}:{len(edges)}"
            edges.append(
                AstEdge(
                    id=eid,
                    type="child",
                    source_id=parent_id,
                    target_id=nid,
                    role="child",
                )
            )
        return nid

    walk(root, None)
    return AstBuildResult(nodes=nodes, edges=edges)
