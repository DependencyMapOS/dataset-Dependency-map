from __future__ import annotations

from tree_sitter import Node

from repo_analysis.models.function_record import DfgEdgeRecord


def _nid(n: Node) -> str:
    return f"ts:{n.start_byte}:{n.end_byte}:{n.type}"


def _txt(n: Node, source: bytes) -> str:
    return source[n.start_byte : n.end_byte].decode("utf-8")


def extract_dfg_edges(body: Node, source: bytes, language: str) -> list[DfgEdgeRecord]:
    """Lightweight def→use edges within a function/method body subtree."""
    if language == "python":
        return _dfg_python(body, source)
    if language in ("javascript", "typescript"):
        return _dfg_js(body, source)
    return []


def _dfg_python(body: Node, source: bytes) -> list[DfgEdgeRecord]:
    edges: list[DfgEdgeRecord] = []
    last_def: dict[str, str] = {}

    def visit(n: Node) -> None:
        if n.type == "assignment":
            left = n.child_by_field_name("left")
            right = n.child_by_field_name("right")
            targets: list[Node] = []
            if left is not None:
                if left.type == "identifier":
                    targets.append(left)
                elif left.type in ("pattern_list", "tuple_pattern"):
                    for ch in left.named_children:
                        if ch.type == "identifier":
                            targets.append(ch)
            for t in targets:
                name = _txt(t, source)
                if name:
                    last_def[name] = _nid(t)
            if right is not None:
                visit(right)
            return
        if n.type == "identifier":
            name = _txt(n, source)
            if name in last_def:
                edges.append(
                    DfgEdgeRecord(
                        var_name=name,
                        def_node_id=last_def[name],
                        use_node_id=_nid(n),
                    )
                )
        for c in n.named_children:
            visit(c)

    for stmt in body.named_children:
        visit(stmt)

    seen: set[tuple[str, str, str]] = set()
    out: list[DfgEdgeRecord] = []
    for e in edges:
        key = (e.var_name, e.def_node_id, e.use_node_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def _dfg_js(body: Node, source: bytes) -> list[DfgEdgeRecord]:
    edges: list[DfgEdgeRecord] = []
    last_def: dict[str, str] = {}

    def walk(n: Node) -> None:
        if n.type == "lexical_declaration":
            for decl in n.named_children:
                if decl.type == "variable_declarator":
                    name_node = decl.child_by_field_name("name")
                    if name_node is None:
                        for ch in decl.named_children:
                            if ch.type == "identifier":
                                name_node = ch
                                break
                    if name_node is not None and name_node.type == "identifier":
                        name = _txt(name_node, source)
                        if name:
                            last_def[name] = _nid(name_node)
        elif n.type == "identifier":
            name = _txt(n, source)
            parent = n.parent
            if parent is not None and parent.type == "variable_declarator":
                return
            if name in last_def:
                edges.append(
                    DfgEdgeRecord(
                        var_name=name,
                        def_node_id=last_def[name],
                        use_node_id=_nid(n),
                    )
                )
        for c in n.named_children:
            walk(c)

    walk(body)
    seen: set[tuple[str, str, str]] = set()
    out: list[DfgEdgeRecord] = []
    for e in edges:
        key = (e.var_name, e.def_node_id, e.use_node_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out
