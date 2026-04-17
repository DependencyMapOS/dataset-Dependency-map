from __future__ import annotations

from repo_analysis.discovery.language_detect import tree_sitter_language_name
from repo_analysis.extraction.dfg import extract_dfg_edges
from repo_analysis.parsing.registry import get_parser_for_language


def test_dfg_python_simple_assignment_and_use() -> None:
    src = b"def f():\n    a = 1\n    b = a\n"
    lang = "python"
    parser = get_parser_for_language(lang)
    tree = parser.parse(src)
    func = tree.root_node.named_children[0]
    assert func.type == "function_definition"
    body = func.child_by_field_name("body")
    assert body is not None
    edges = extract_dfg_edges(body, src, lang)
    assert any(e.var_name == "a" for e in edges)


def test_dfg_javascript_let_and_use() -> None:
    src = b"function f() {\n  let x = 1;\n  return x;\n}\n"
    lang = tree_sitter_language_name("javascript")
    parser = get_parser_for_language(lang)
    tree = parser.parse(src)
    func = tree.root_node.named_children[0]
    assert func.type == "function_declaration"
    body = func.child_by_field_name("body")
    assert body is not None
    edges = extract_dfg_edges(body, src, "javascript")
    assert any(e.var_name == "x" for e in edges)
