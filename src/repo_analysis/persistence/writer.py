from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel


def write_jsonl_lines_capped(path: Path, lines: list[str], max_bytes: int) -> str:
    """
    Write JSONL from lines (each line should end with \\n). If total size exceeds max_bytes,
    write stem_partNNN.jsonl shards and stem_index.json. Returns basename written (single file or index).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    suffix = path.suffix

    normed = [ln if ln.endswith("\n") else ln + "\n" for ln in lines]
    total = sum(len(x.encode("utf-8")) for x in normed)
    if total <= max_bytes:
        path.write_text("".join(normed), encoding="utf-8")
        return path.name

    parts: list[str] = []
    current: list[str] = []
    cur_b = 0
    part_idx = 0

    def flush() -> None:
        nonlocal part_idx, current, cur_b
        if not current:
            return
        fname = f"{stem}_part{part_idx:03d}{suffix}"
        (path.parent / fname).write_text("".join(current), encoding="utf-8")
        parts.append(fname)
        part_idx += 1
        current.clear()
        cur_b = 0

    for ln in normed:
        b = len(ln.encode("utf-8"))
        if b > max_bytes:
            msg = f"single JSONL record exceeds max_bytes ({b} > {max_bytes})"
            raise ValueError(msg)
        if current and cur_b + b > max_bytes:
            flush()
        current.append(ln)
        cur_b += b
    flush()

    index_path = path.parent / f"{stem}_index.json"
    payload = {
        "shard_format_version": 1,
        "max_part_bytes": max_bytes,
        "part_count": len(parts),
        "parts": parts,
    }
    index_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return index_path.name


def write_jsonl_models_capped(path: Path, models: Sequence[BaseModel], max_bytes: int) -> str:
    lines = [m.model_dump_json() + "\n" for m in models]
    return write_jsonl_lines_capped(path, lines, max_bytes)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="manifest-", suffix=".json", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def write_jsonl(path: Path, lines: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for line in lines:
            f.write(json.dumps(line, sort_keys=True) + "\n")


def write_jsonl_models(path: Path, models: Sequence[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for m in models:
            f.write(m.model_dump_json() + "\n")
