from __future__ import annotations

import json
from pathlib import Path

from repo_analysis.export import split_combined
from repo_analysis.models.ast import AstCombinedArtifact, AstEdge, AstNode, SourcePosition, SourceSpan


def _span() -> SourceSpan:
    return SourceSpan(
        start_byte=0,
        end_byte=1,
        start=SourcePosition(line=1, column=0),
        end=SourcePosition(line=1, column=1),
    )


def _artifact_with_nodes(count: int) -> AstCombinedArtifact:
    nodes = [
        AstNode(id=f"n{i}", kind="k", span=_span(), label="") for i in range(count)
    ]
    edges: list[AstEdge] = []
    for i in range(count - 1):
        edges.append(
            AstEdge(
                id=f"e{i}",
                type="child",
                source_id=f"n{i}",
                target_id=f"n{i + 1}",
            )
        )
    return AstCombinedArtifact(
        repository_name="r",
        repository_url="u",
        branch="b",
        commit_sha="c",
        analysis_timestamp="t",
        source_language="py",
        relative_path="",
        parser_id="p",
        generation_version="1",
        dependency_resolution_status="ok",
        warnings=[],
        errors=[],
        nodes=nodes,
        edges=edges,
    )


def test_split_produces_multiple_parts_under_budget(tmp_path: Path) -> None:
    model = _artifact_with_nodes(20)
    split_combined.write_split_combined_json_and_graphml(
        model=model,
        out_dir=tmp_path,
        graph_kind="ast",
        commit_sha="c",
        tool_version="1",
        max_bytes=4096,
    )
    idx = json.loads((tmp_path / "combined_index.json").read_text(encoding="utf-8"))
    assert idx["part_count"] >= 2
    for p in idx["parts"]:
        jp = tmp_path / p["json"]
        assert jp.stat().st_size <= split_combined.DEFAULT_MAX_PART_BYTES
        gp = tmp_path / p["graphml"]
        assert gp.exists()
    assert not (tmp_path / "combined.json").exists()


def test_split_empty_graph_writes_index_only(tmp_path: Path) -> None:
    empty = AstCombinedArtifact(
        repository_name="r",
        repository_url="u",
        branch="b",
        commit_sha="c",
        analysis_timestamp="t",
        source_language="py",
        relative_path="",
        parser_id="p",
        generation_version="1",
        dependency_resolution_status="ok",
        warnings=[],
        errors=[],
        nodes=[],
        edges=[],
    )
    split_combined.write_split_combined_json_and_graphml(
        model=empty,
        out_dir=tmp_path,
        graph_kind="ast",
        commit_sha="c",
        tool_version="1",
        max_bytes=1024,
    )
    idx = json.loads((tmp_path / "combined_index.json").read_text(encoding="utf-8"))
    assert idx["part_count"] == 0
    assert idx["parts"] == []
