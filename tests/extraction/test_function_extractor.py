from __future__ import annotations

from repo_analysis.extraction.function_extractor import (
    ExtractContext,
    extract_functions_from_source,
)
from repo_analysis.parsing.registry import get_parser_for_language


def _parse(src: bytes, lang: str):
    p = get_parser_for_language(lang)
    return p.parse(src).root_node


def test_docstring_and_comments_and_types_python() -> None:
    src = b'''def foo(a: int) -> None:\n    """doc here"""\n    # inline\n    x = 1\n    return x\n'''
    root = _parse(src, "python")
    ctx = ExtractContext(
        repo_name="r",
        rel_path="m.py",
        commit_sha="c0ffee",
        module_path="m.py",
        language="python",
        known_function_ids=set(),
    )
    recs = extract_functions_from_source(ctx=ctx, source=src, tree_root=root, known_names={"foo"})
    assert len(recs) == 1
    r = recs[0]
    assert r.docstring is not None and "doc here" in r.docstring
    assert any("inline" in c.text for c in r.comments)
    assert any(t.annotation_text.strip() == "int" for t in r.type_annotations)


def test_stable_id_across_runs_python() -> None:
    src = b"def bar():\n    return 1\n"
    root = _parse(src, "python")

    def run() -> str:
        ctx = ExtractContext(
            repo_name="repo",
            rel_path="x.py",
            commit_sha="deadbeef",
            module_path="x.py",
            language="python",
            known_function_ids=set(),
        )
        recs = extract_functions_from_source(
            ctx=ctx, source=src, tree_root=root, known_names={"bar"}
        )
        return recs[0].id

    assert run() == run()
