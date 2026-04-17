from __future__ import annotations

import re
from dataclasses import dataclass

from tree_sitter import Node

from repo_analysis.extraction.dfg import extract_dfg_edges
from repo_analysis.models.function_record import (
    CallEdgeRecord,
    CommentLine,
    FunctionRecord,
    FunctionSpan,
    SourcePoint,
    TypeAnnotationRecord,
)
from repo_analysis.parsing.registry import get_parser_for_language


def _tokenize(code: str) -> list[str]:
    return [t for t in re.split(r"\s+", code.strip()) if t]


def _span_from_node(n: Node) -> FunctionSpan:
    return FunctionSpan(
        start=SourcePoint(line=int(n.start_point.row) + 1, col=int(n.start_point.column)),
        end=SourcePoint(line=int(n.end_point.row) + 1, col=int(n.end_point.column)),
    )


def _extract_line_comments(source: bytes, start_line: int, end_line: int, language: str) -> list[CommentLine]:
    lines = source.decode("utf-8", errors="replace").splitlines()
    out: list[CommentLine] = []
    for i in range(max(0, start_line - 1), min(len(lines), end_line)):
        line_no = i + 1
        text = lines[i]
        if language == "python" and "#" in text:
            idx = text.index("#")
            out.append(CommentLine(line=line_no, text=text[idx:].strip()))
        elif language in ("javascript", "typescript") and "//" in text:
            idx = text.index("//")
            out.append(CommentLine(line=line_no, text=text[idx:].strip()))
    return out


def _first_string_node(node: Node) -> Node | None:
    if node.type == "string":
        return node
    for c in node.named_children:
        found = _first_string_node(c)
        if found is not None:
            return found
    return None


def _py_docstring(body: Node, source: bytes) -> str | None:
    if not body.named_children:
        return None
    first = body.named_children[0]
    if first.type == "string":
        return source[first.start_byte : first.end_byte].decode("utf-8", errors="replace")
    if first.type == "expression_statement":
        inner = _first_string_node(first)
        if inner is None:
            return None
        return source[inner.start_byte : inner.end_byte].decode("utf-8", errors="replace")
    return None


def _py_type_annotations(func: Node, source: bytes) -> list[TypeAnnotationRecord]:
    out: list[TypeAnnotationRecord] = []
    params = func.child_by_field_name("parameters")
    if params is None:
        return out
    for ch in params.named_children:
        if ch.type == "typed_parameter":
            ident = ch.child_by_field_name("name")
            if ident is None and ch.named_children:
                ident = ch.named_children[0]
            typ = ch.child_by_field_name("type")
            if ident is None or typ is None:
                continue
            out.append(
                TypeAnnotationRecord(
                    node_id=f"ts:{ident.start_byte}:{ident.end_byte}:{ident.type}",
                    annotation_text=source[typ.start_byte : typ.end_byte].decode("utf-8", errors="replace"),
                )
            )
    ret = func.child_by_field_name("return_type")
    if ret is not None:
        out.append(
            TypeAnnotationRecord(
                node_id="return",
                annotation_text=source[ret.start_byte : ret.end_byte].decode("utf-8", errors="replace"),
            )
        )
    return out


def _function_id(
    repo_name: str,
    rel_path: str,
    parent_class: str | None,
    func_name: str,
    overload_index: int,
) -> str:
    cls = parent_class or ""
    return f"{repo_name}:{rel_path}:{cls}:{func_name}:{overload_index}"


@dataclass
class ExtractContext:
    repo_name: str
    rel_path: str
    commit_sha: str
    module_path: str
    language: str
    known_function_ids: set[str]


def extract_functions_from_source(
    *,
    ctx: ExtractContext,
    source: bytes,
    tree_root: Node,
    known_names: set[str] | None = None,
) -> list[FunctionRecord]:
    names = known_names if known_names is not None else set()
    if ctx.language == "python":
        return _extract_python(ctx, source, tree_root, names)
    if ctx.language in ("javascript", "typescript"):
        return _extract_js(ctx, source, tree_root, names)
    return []


def _extract_python(ctx: ExtractContext, source: bytes, root: Node, known_names: set[str]) -> list[FunctionRecord]:
    out: list[FunctionRecord] = []
    overload: dict[tuple[str, str | None], int] = {}

    def visit_class(class_node: Node) -> None:
        cname = ""
        for ch in class_node.named_children:
            if ch.type == "identifier":
                cname = source[ch.start_byte : ch.end_byte].decode("utf-8", errors="replace")
                break
        for ch in class_node.named_children:
            if ch.type == "function_definition":
                out.append(
                    _py_function(
                        ctx,
                        source,
                        ch,
                        parent_class=cname,
                        overload=overload,
                        known_names=known_names,
                    )
                )

    def visit(n: Node) -> None:
        if n.type == "class_definition":
            visit_class(n)
        elif n.type == "function_definition":
            out.append(
                _py_function(ctx, source, n, parent_class=None, overload=overload, known_names=known_names)
            )
        for c in n.named_children:
            visit(c)

    visit(root)
    return out


def _py_function(
    ctx: ExtractContext,
    source: bytes,
    func: Node,
    *,
    parent_class: str | None,
    overload: dict[tuple[str, str | None], int],
    known_names: set[str],
) -> FunctionRecord:
    name = ""
    for ch in func.named_children:
        if ch.type == "identifier":
            name = source[ch.start_byte : ch.end_byte].decode("utf-8", errors="replace")
            break
    body = func.child_by_field_name("body")
    if body is None:
        body = func
    doc = _py_docstring(body, source) if body else None
    sig_end = body.start_byte if body else func.end_byte
    signature_src = source[func.start_byte : sig_end].decode("utf-8", errors="replace")
    body_start = body.start_byte if body else func.end_byte
    if body is not None and body.named_children and body.named_children[0].type == "string" and doc:
        if len(body.named_children) > 1:
            body_start = body.named_children[1].start_byte
        else:
            body_start = body.end_byte
    body_src = source[body_start : body.end_byte].decode("utf-8", errors="replace") if body else ""

    key = (name, parent_class)
    idx = overload.get(key, 0)
    overload[key] = idx + 1
    fid = _function_id(ctx.repo_name, ctx.rel_path, parent_class, name, idx)
    ctx.known_function_ids.add(fid)

    dfg = extract_dfg_edges(body, source, "python") if body else []
    types = _py_type_annotations(func, source)
    comments = _extract_line_comments(
        source,
        int(func.start_point.row) + 1,
        int(func.end_point.row) + 1,
        "python",
    )
    calls = _py_call_edges(func, source, known_names)

    return FunctionRecord(
        id=fid,
        signature_tokens=_tokenize(signature_src),
        body_tokens=_tokenize(body_src),
        docstring=doc,
        comments=comments,
        span=_span_from_node(func),
        parent_class=parent_class,
        module_path=ctx.module_path,
        language=ctx.language,
        dfg_edges=dfg,
        call_edges=calls,
        type_annotations=types,
    )


def _py_call_edges(func: Node, source: bytes, known_names: set[str]) -> list[CallEdgeRecord]:
    edges: list[CallEdgeRecord] = []
    callee_names: list[str] = []

    def rec(n: Node) -> None:
        if n.type == "call":
            fn = n.child_by_field_name("function")
            if fn is not None and fn.type == "identifier":
                callee_names.append(source[fn.start_byte : fn.end_byte].decode("utf-8", errors="replace"))
        for c in n.named_children:
            rec(c)

    rec(func)
    for name in callee_names:
        resolved = name in known_names
        edges.append(CallEdgeRecord(callee_id=name, resolved=resolved))
    return edges


def _extract_js(ctx: ExtractContext, source: bytes, root: Node, known_names: set[str]) -> list[FunctionRecord]:
    out: list[FunctionRecord] = []
    overload: dict[tuple[str, str | None], int] = {}

    def visit(n: Node) -> None:
        if n.type == "function_declaration":
            out.append(_js_function(ctx, source, n, None, overload, known_names))
        elif n.type == "class_declaration":
            cname = ""
            for ch in n.named_children:
                if ch.type == "identifier":
                    cname = source[ch.start_byte : ch.end_byte].decode("utf-8", errors="replace")
                    break
            for ch in n.named_children:
                if ch.type == "class_body":
                    for m in ch.named_children:
                        if m.type == "method_definition":
                            out.append(_js_function(ctx, source, m, cname, overload, known_names))
        for c in n.named_children:
            visit(c)

    visit(root)
    return out


def _js_function(
    ctx: ExtractContext,
    source: bytes,
    func: Node,
    parent_class: str | None,
    overload: dict[tuple[str, str | None], int],
    known_names: set[str],
) -> FunctionRecord:
    name = ""
    for ch in func.named_children:
        if ch.type == "identifier":
            name = source[ch.start_byte : ch.end_byte].decode("utf-8", errors="replace")
            break
    body = func.child_by_field_name("body")
    if body is None:
        body = func
    doc = None
    signature_src = source[func.start_byte : body.start_byte].decode("utf-8", errors="replace")
    body_src = source[body.start_byte : body.end_byte].decode("utf-8", errors="replace")
    key = (name, parent_class)
    idx = overload.get(key, 0)
    overload[key] = idx + 1
    fid = _function_id(ctx.repo_name, ctx.rel_path, parent_class, name, idx)
    ctx.known_function_ids.add(fid)
    dfg = extract_dfg_edges(body, source, ctx.language) if body else []
    comments = _extract_line_comments(
        source,
        int(func.start_point.row) + 1,
        int(func.end_point.row) + 1,
        ctx.language,
    )
    calls = _js_call_edges(func, source, known_names)
    return FunctionRecord(
        id=fid,
        signature_tokens=_tokenize(signature_src),
        body_tokens=_tokenize(body_src),
        docstring=doc,
        comments=comments,
        span=_span_from_node(func),
        parent_class=parent_class,
        module_path=ctx.module_path,
        language=ctx.language,
        dfg_edges=dfg,
        call_edges=calls,
        type_annotations=[],
    )


def _js_call_edges(func: Node, source: bytes, known_names: set[str]) -> list[CallEdgeRecord]:
    names: list[str] = []

    def rec(n: Node) -> None:
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn is not None and fn.type == "identifier":
                names.append(source[fn.start_byte : fn.end_byte].decode("utf-8", errors="replace"))
        for c in n.named_children:
            rec(c)

    rec(func)
    out: list[CallEdgeRecord] = []
    for name in names:
        resolved = name in known_names
        out.append(CallEdgeRecord(callee_id=name, resolved=resolved))
    return out


def _collect_function_names_first_pass(files: list[tuple[str, bytes, str]], repo_name: str) -> set[str]:
    names: set[str] = set()
    for rel, src, lang in files:
        try:
            parser = get_parser_for_language(lang)
        except Exception:
            continue
        tree = parser.parse(src)
        ctx = ExtractContext(
            repo_name=repo_name,
            rel_path=rel,
            commit_sha="",
            module_path=rel.replace("\\", "/"),
            language=lang,
            known_function_ids=set(),
        )
        recs = extract_functions_from_source(ctx=ctx, source=src, tree_root=tree.root_node, known_names=set())
        for r in recs:
            short = r.id.split(":")[-2]
            names.add(short)
    return names


def extract_repo_functions(
    *,
    repo_root_name: str,
    commit_sha: str,
    files: list[tuple[str, bytes, str]],
) -> list[FunctionRecord]:
    """Extract functions from multiple files; `files` entries are (rel_path, source, language)."""
    known_names = _collect_function_names_first_pass(files, repo_root_name)
    out: list[FunctionRecord] = []
    for rel, src, lang in files:
        try:
            parser = get_parser_for_language(lang)
        except Exception:
            continue
        tree = parser.parse(src)
        ctx = ExtractContext(
            repo_name=repo_root_name,
            rel_path=rel,
            commit_sha=commit_sha,
            module_path=rel.replace("\\", "/"),
            language=lang,
            known_function_ids=set(),
        )
        out.extend(
            extract_functions_from_source(
                ctx=ctx,
                source=src,
                tree_root=tree.root_node,
                known_names=known_names,
            )
        )
    return out
