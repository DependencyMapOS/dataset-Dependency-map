from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from tree_sitter import Node

from repo_analysis.models.asg import AsgEdge, AsgNode


@dataclass
class AsgBuildResult:
    nodes: list[AsgNode]
    edges: list[AsgEdge]


def _text(source: bytes, node: Node) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _find_children_types(root: Node, type_name: str) -> list[Node]:
    out: list[Node] = []

    def rec(n: Node) -> None:
        if n.type == type_name:
            out.append(n)
        for c in n.named_children:
            rec(c)

    rec(root)
    return out


def build_asg_for_tree(
    *,
    commit_sha: str,
    relative_path: str,
    language: str,
    root: Node,
    source: bytes,
) -> AsgBuildResult:
    """Heuristic ASG: module, imports, defs, calls (tree-sitter only)."""
    ordinal: dict[str, int] = defaultdict(int)

    def next_id(kind: str) -> str:
        ordinal[kind] += 1
        return f"asg:{commit_sha}:{relative_path}:{kind}:{ordinal[kind]}"

    nodes: list[AsgNode] = []
    edges: list[AsgEdge] = []
    ecount = 0

    def add_edge(etype: str, src: str, tgt: str) -> None:
        nonlocal ecount
        ecount += 1
        edges.append(
            AsgEdge(
                id=f"asg:{commit_sha}:{relative_path}:edge:{ecount}",
                type=etype,
                source_id=src,
                target_id=tgt,
            )
        )

    mod_id = next_id("module")
    nodes.append(
        AsgNode(
            id=mod_id,
            kind="module",
            label=relative_path,
            payload={"path": relative_path},
        )
    )

    if language == "python":
        _python_asg(root, source, mod_id, next_id, add_edge, nodes)
    elif language in ("javascript", "typescript"):
        _js_asg(root, source, mod_id, next_id, add_edge, nodes)
    else:
        _generic_asg(root, source, mod_id, next_id, add_edge, nodes, language)

    return AsgBuildResult(nodes=nodes, edges=edges)


def _python_asg(
    root: Node,
    source: bytes,
    mod_id: str,
    next_id: Callable[[str], str],
    add_edge: Callable[[str, str, str], None],
    nodes: list[AsgNode],
) -> None:
    for n in _find_children_types(root, "import_statement"):
        iid = next_id("import")
        nodes.append(AsgNode(id=iid, kind="import", label=_text(source, n)[:200], payload={}))
        add_edge("imports", mod_id, iid)
    for n in _find_children_types(root, "import_from_statement"):
        iid = next_id("import")
        nodes.append(AsgNode(id=iid, kind="import", label=_text(source, n)[:200], payload={}))
        add_edge("imports", mod_id, iid)
    for n in _find_children_types(root, "function_definition"):
        fid = next_id("symbol_def")
        name = ""
        for ch in n.named_children:
            if ch.type == "identifier":
                name = _text(source, ch)
                break
        nodes.append(
            AsgNode(
                id=fid,
                kind="symbol_def",
                label=name or "(anonymous)",
                payload={"construct": "function"},
            )
        )
        add_edge("defines", mod_id, fid)
    for n in _find_children_types(root, "class_definition"):
        cid = next_id("symbol_def")
        name = ""
        for ch in n.named_children:
            if ch.type == "identifier":
                name = _text(source, ch)
                break
        nodes.append(
            AsgNode(
                id=cid,
                kind="symbol_def",
                label=name or "(class)",
                payload={"construct": "class"},
            )
        )
        add_edge("defines", mod_id, cid)
    for n in _find_children_types(root, "call"):
        call_id = next_id("call")
        label = _text(source, n)[:200]
        nodes.append(AsgNode(id=call_id, kind="call", label=label, payload={}))
        add_edge("calls", mod_id, call_id)


def _js_asg(
    root: Node,
    source: bytes,
    mod_id: str,
    next_id: Callable[[str], str],
    add_edge: Callable[[str, str, str], None],
    nodes: list[AsgNode],
) -> None:
    for n in _find_children_types(root, "import_statement"):
        iid = next_id("import")
        nodes.append(AsgNode(id=iid, kind="import", label=_text(source, n)[:200], payload={}))
        add_edge("imports", mod_id, iid)
    for n in _find_children_types(root, "function_declaration"):
        fid = next_id("symbol_def")
        name = ""
        for ch in n.named_children:
            if ch.type == "identifier":
                name = _text(source, ch)
                break
        nodes.append(
            AsgNode(
                id=fid,
                kind="symbol_def",
                label=name or "(anonymous)",
                payload={"construct": "function"},
            )
        )
        add_edge("defines", mod_id, fid)
    for n in _find_children_types(root, "call_expression"):
        call_id = next_id("call")
        label = _text(source, n)[:200]
        nodes.append(AsgNode(id=call_id, kind="call", label=label, payload={}))
        add_edge("calls", mod_id, call_id)


def _generic_asg(
    root: Node,
    source: bytes,
    mod_id: str,
    next_id: Callable[[str], str],
    add_edge: Callable[[str, str, str], None],
    nodes: list[AsgNode],
    language: str,
) -> None:
    _ = language
    for n in root.named_children:
        if n.type.endswith("import") or n.type.startswith("import"):
            iid = next_id("import")
            nodes.append(AsgNode(id=iid, kind="import", label=_text(source, n)[:200], payload={}))
            add_edge("imports", mod_id, iid)
