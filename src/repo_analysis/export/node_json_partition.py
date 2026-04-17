from __future__ import annotations

import json
from typing import Any, Literal

# GitHub warns at 50 MB; cap dataset artifacts per file.
DATASET_MAX_FILE_BYTES = 50 * 1024 * 1024


def json_utf8_bytes(obj: Any, *, indent: int | None = 2) -> int:
    """Serialized UTF-8 size; must match how we write JSON to disk (indent=2 by default)."""
    return len(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=indent).encode("utf-8")
    )


def edges_for_node_ids(edges: list[dict[str, Any]], ids: set[str]) -> list[dict[str, Any]]:
    return [e for e in edges if e.get("source_id") in ids]


def partition_node_ranges(
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
            ce = edges_for_node_ids(edges, ids)
            payload = {
                **base,
                "nodes": nodes[start:mid],
                "edges": ce,
                "shard_format_version": 1,
                "part_index": 0,
                "part_count": n,
                "graph_kind": graph_kind,
            }
            if json_utf8_bytes(payload, indent=2) <= budget:
                best = mid
                lo = mid + 1
            else:
                hi = mid - 1

        if best == start:
            best = start + 1

        ranges.append((start, best))
        start = best

    return ranges
