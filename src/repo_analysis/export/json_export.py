from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from repo_analysis.export.node_json_partition import (
    edges_for_node_ids,
    json_utf8_bytes,
    partition_node_ranges,
)


def write_json(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = json.loads(model.model_dump_json())
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def _write_json_shard_file(path: Path, shard: dict[str, Any], max_bytes: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(shard, indent=2, sort_keys=True, ensure_ascii=False)
    if len(text.encode("utf-8")) <= max_bytes:
        path.write_text(text, encoding="utf-8")
        return
    text = json.dumps(shard, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    if path.stat().st_size > max_bytes:
        msg = f"JSON shard exceeds max_bytes ({path.stat().st_size} > {max_bytes})"
        raise ValueError(msg)


def write_json_capped(
    path: Path,
    model: BaseModel,
    *,
    max_bytes: int,
    graph_kind: Literal["ast", "asg"],
) -> None:
    """
    Write a per-file AST/ASG artifact. If the full JSON exceeds max_bytes, write
    {stem}_index.json plus {stem}_partNNN.json shards (same directory as path).
    """
    data = json.loads(model.model_dump_json())
    nodes = data.pop("nodes")
    edges = data.pop("edges")
    base_meta = data
    rel = str(base_meta.get("relative_path", ""))

    single: dict[str, Any] = {**base_meta, "nodes": nodes, "edges": edges}
    if json_utf8_bytes(single, indent=2) <= max_bytes:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(single, indent=2, sort_keys=True, ensure_ascii=False),
            encoding="utf-8",
        )
        return

    ranges = partition_node_ranges(nodes, edges, base_meta, max_bytes, graph_kind)
    stem = path.stem
    part_names: list[str] = []
    for part_index, (a, b) in enumerate(ranges):
        ids = {nodes[i]["id"] for i in range(a, b)}
        ce = edges_for_node_ids(edges, ids)
        shard = {
            **base_meta,
            "nodes": nodes[a:b],
            "edges": ce,
            "shard_format_version": 1,
            "part_index": part_index,
            "part_count": len(ranges),
            "graph_kind": graph_kind,
        }
        part_name = f"{stem}_part{part_index:03d}.json"
        part_names.append(part_name)
        _write_json_shard_file(path.parent / part_name, shard, max_bytes)

    index_payload = {
        "shard_format_version": 1,
        "graph_kind": graph_kind,
        "artifact_kind": "ast_per_file" if graph_kind == "ast" else "asg_per_file",
        "relative_path": rel,
        "max_part_bytes": max_bytes,
        "part_count": len(ranges),
        "parts": part_names,
    }
    index_path = path.parent / f"{stem}_index.json"
    index_path.write_text(
        json.dumps(index_payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding="utf-8",
    )
