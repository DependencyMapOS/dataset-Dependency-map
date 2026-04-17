from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from repo_analysis.export import graphml_export
from repo_analysis.export.node_json_partition import (
    DATASET_MAX_FILE_BYTES,
    edges_for_node_ids,
    json_utf8_bytes,
    partition_node_ranges,
)

# Backwards-compatible alias
DEFAULT_MAX_PART_BYTES = DATASET_MAX_FILE_BYTES


def _compact_json_bytes(obj: dict[str, Any]) -> int:
    return len(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _shard_fits_json_graphml(
    a: int,
    b: int,
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    base_meta: dict[str, Any],
    g_nodes: list[dict[str, Any]],
    g_edges: list[dict[str, Any]],
    max_bytes: int,
    graph_kind: Literal["ast", "asg"],
    commit_sha: str,
    tool_version: str,
) -> bool:
    ids = {nodes[i]["id"] for i in range(a, b)}
    ce = edges_for_node_ids(edges, ids)
    shard = {
        **base_meta,
        "nodes": nodes[a:b],
        "edges": ce,
        "shard_format_version": 1,
        "part_index": 0,
        "part_count": 1,
        "graph_kind": graph_kind,
    }
    if json_utf8_bytes(shard, indent=2) > max_bytes and _compact_json_bytes(shard) > max_bytes:
        return False

    gn = [x for x in g_nodes if str(x.get("id")) in ids]
    ge = [x for x in g_edges if str(x.get("source")) in ids]
    with tempfile.NamedTemporaryFile(suffix=".graphml", delete=False) as tf:
        gpath = Path(tf.name)
    try:
        graphml_export.write_graphml(
            gpath,
            graph_kind=graph_kind,
            nodes=gn,
            edges=ge,
            commit_sha=commit_sha,
            tool_version=tool_version,
            compact=False,
        )
        if gpath.stat().st_size <= max_bytes:
            return True
        graphml_export.write_graphml(
            gpath,
            graph_kind=graph_kind,
            nodes=gn,
            edges=ge,
            commit_sha=commit_sha,
            tool_version=tool_version,
            compact=True,
        )
        return gpath.stat().st_size <= max_bytes
    finally:
        gpath.unlink(missing_ok=True)


def _refine_for_graphml(
    a: int,
    b: int,
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    base_meta: dict[str, Any],
    g_nodes: list[dict[str, Any]],
    g_edges: list[dict[str, Any]],
    max_bytes: int,
    graph_kind: Literal["ast", "asg"],
    commit_sha: str,
    tool_version: str,
) -> list[tuple[int, int]]:
    if a >= b:
        return []
    if _shard_fits_json_graphml(
        a,
        b,
        nodes=nodes,
        edges=edges,
        base_meta=base_meta,
        g_nodes=g_nodes,
        g_edges=g_edges,
        max_bytes=max_bytes,
        graph_kind=graph_kind,
        commit_sha=commit_sha,
        tool_version=tool_version,
    ):
        return [(a, b)]
    if b - a <= 1:
        return [(a, b)]
    mid = (a + b) // 2
    return (
        _refine_for_graphml(
            a,
            mid,
            nodes=nodes,
            edges=edges,
            base_meta=base_meta,
            g_nodes=g_nodes,
            g_edges=g_edges,
            max_bytes=max_bytes,
            graph_kind=graph_kind,
            commit_sha=commit_sha,
            tool_version=tool_version,
        )
        + _refine_for_graphml(
            mid,
            b,
            nodes=nodes,
            edges=edges,
            base_meta=base_meta,
            g_nodes=g_nodes,
            g_edges=g_edges,
            max_bytes=max_bytes,
            graph_kind=graph_kind,
            commit_sha=commit_sha,
            tool_version=tool_version,
        )
    )


def _write_json_shard(path: Path, shard: dict[str, Any], max_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(shard, indent=2, sort_keys=True, ensure_ascii=False)
    if len(text.encode("utf-8")) <= max_bytes:
        path.write_text(text, encoding="utf-8")
        return
    text = json.dumps(shard, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    if path.stat().st_size > max_bytes:
        msg = f"combined JSON shard exceeds max_bytes ({path.stat().st_size} > {max_bytes})"
        raise ValueError(msg)


def _write_graphml_shard(
    path: Path,
    *,
    graph_kind: str,
    gn: list[dict[str, Any]],
    ge: list[dict[str, Any]],
    commit_sha: str,
    tool_version: str,
    max_bytes: int,
) -> None:
    graphml_export.write_graphml(
        path,
        graph_kind=graph_kind,
        nodes=gn,
        edges=ge,
        commit_sha=commit_sha,
        tool_version=tool_version,
        compact=False,
    )
    if path.stat().st_size <= max_bytes:
        return
    graphml_export.write_graphml(
        path,
        graph_kind=graph_kind,
        nodes=gn,
        edges=ge,
        commit_sha=commit_sha,
        tool_version=tool_version,
        compact=True,
    )
    if path.stat().st_size > max_bytes:
        msg = f"combined GraphML shard exceeds max_bytes ({path.stat().st_size} > {max_bytes})"
        raise ValueError(msg)


def write_split_combined_json_and_graphml(
    *,
    model: BaseModel,
    out_dir: Path,
    graph_kind: Literal["ast", "asg"],
    commit_sha: str,
    tool_version: str,
    max_bytes: int = DEFAULT_MAX_PART_BYTES,
) -> Path:
    """
    Write combined artifact as combined_index.json plus combined_partNNN.json / .graphml shards.
    Does not write monolithic combined.json / combined.graphml (avoids huge single files).
    Each shard JSON and GraphML file is kept at or below max_bytes when possible.
    """
    data = json.loads(model.model_dump_json())
    nodes = data.pop("nodes")
    edges = data.pop("edges")
    base_meta = data

    coarse = partition_node_ranges(nodes, edges, base_meta, max_bytes, graph_kind)
    g_nodes, g_edges = (
        graphml_export.pydantic_to_graphml_nodes_edges_ast(model)
        if graph_kind == "ast"
        else graphml_export.pydantic_to_graphml_nodes_edges_asg(model)
    )

    ranges: list[tuple[int, int]] = []
    for a, b in coarse:
        ranges.extend(
            _refine_for_graphml(
                a,
                b,
                nodes=nodes,
                edges=edges,
                base_meta=base_meta,
                g_nodes=g_nodes,
                g_edges=g_edges,
                max_bytes=max_bytes,
                graph_kind=graph_kind,
                commit_sha=commit_sha,
                tool_version=tool_version,
            )
        )

    total_parts = len(ranges)

    out_dir.mkdir(parents=True, exist_ok=True)
    part_entries: list[dict[str, str]] = []

    for part_index, (a, b) in enumerate(ranges):
        ids = {nodes[i]["id"] for i in range(a, b)}
        ce = edges_for_node_ids(edges, ids)
        shard = {
            **base_meta,
            "nodes": nodes[a:b],
            "edges": ce,
            "shard_format_version": 1,
            "part_index": part_index,
            "part_count": total_parts,
            "graph_kind": graph_kind,
        }
        stem = f"combined_part{part_index:03d}"
        json_path = out_dir / f"{stem}.json"
        _write_json_shard(json_path, shard, max_bytes)

        id_set = ids
        gn = [x for x in g_nodes if str(x.get("id")) in id_set]
        ge = [x for x in g_edges if str(x.get("source")) in id_set]
        _write_graphml_shard(
            out_dir / f"{stem}.graphml",
            graph_kind=graph_kind,
            gn=gn,
            ge=ge,
            commit_sha=commit_sha,
            tool_version=tool_version,
            max_bytes=max_bytes,
        )
        part_entries.append({"json": f"{stem}.json", "graphml": f"{stem}.graphml"})

    index: dict[str, Any] = {
        "shard_format_version": 1,
        "graph_kind": graph_kind,
        "max_part_bytes": max_bytes,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "part_count": total_parts,
        "parts": part_entries,
        **base_meta,
    }
    index_path = out_dir / "combined_index.json"
    with index_path.open("w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, sort_keys=True)

    return index_path
