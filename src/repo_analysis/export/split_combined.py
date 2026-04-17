from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from repo_analysis.export import graphml_export

# GitHub warns at 50 MB; stay under this for each shard.
DEFAULT_MAX_PART_BYTES = 50 * 1024 * 1024


def _json_utf8_bytes(obj: Any) -> int:
    return len(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8"))


def _edges_for_node_ids(edges: list[dict[str, Any]], ids: set[str]) -> list[dict[str, Any]]:
    return [e for e in edges if e.get("source_id") in ids]


def _partition_node_ranges(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    base: dict[str, Any],
    max_bytes: int,
    graph_kind: Literal["ast", "asg"],
) -> list[tuple[int, int]]:
    """Return half-open ranges [start, end) covering all nodes; each shard <= max_bytes when serialized."""
    n = len(nodes)
    if n == 0:
        return []

    # Reserve bytes for shard envelope keys (part_index, part_count, etc.).
    budget = max(1024, max_bytes - 8192)
    ranges: list[tuple[int, int]] = []
    start = 0
    while start < n:
        lo = start + 1
        hi = n
        best = start + 1
        while lo <= hi:
            mid = (lo + hi) // 2
            ids = {nodes[i]["id"] for i in range(start, mid)}
            ce = _edges_for_node_ids(edges, ids)
            payload = {
                **base,
                "nodes": nodes[start:mid],
                "edges": ce,
                "shard_format_version": 1,
                "part_index": 0,
                "part_count": n,
                "graph_kind": graph_kind,
            }
            if _json_utf8_bytes(payload) <= budget:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1

        if best == start:
            # Single node (or first batch) still too large — force one node and accept oversize.
            best = start + 1

        ranges.append((start, best))
        start = best

    return ranges


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
    """
    data = json.loads(model.model_dump_json())
    nodes = data.pop("nodes")
    edges = data.pop("edges")
    base_meta = data

    ranges = _partition_node_ranges(nodes, edges, base_meta, max_bytes, graph_kind)
    total_parts = len(ranges)

    out_dir.mkdir(parents=True, exist_ok=True)
    part_entries: list[dict[str, str]] = []

    g_nodes, g_edges = (
        graphml_export.pydantic_to_graphml_nodes_edges_ast(model)
        if graph_kind == "ast"
        else graphml_export.pydantic_to_graphml_nodes_edges_asg(model)
    )

    for part_index, (a, b) in enumerate(ranges):
        ids = {nodes[i]["id"] for i in range(a, b)}
        ce = _edges_for_node_ids(edges, ids)
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
        with json_path.open("w", encoding="utf-8") as f:
            json.dump(shard, f, indent=2, sort_keys=True)

        id_set = ids
        gn = [x for x in g_nodes if str(x.get("id")) in id_set]
        ge = [x for x in g_edges if str(x.get("source")) in id_set]
        graphml_export.write_graphml(
            out_dir / f"{stem}.graphml",
            graph_kind=graph_kind,
            nodes=gn,
            edges=ge,
            commit_sha=commit_sha,
            tool_version=tool_version,
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
