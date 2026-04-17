from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from repo_analysis.persistence.writer import write_jsonl_lines_capped, write_jsonl_models_capped


class _M(BaseModel):
    x: int


def test_jsonl_single_file_when_under_cap(tmp_path: Path) -> None:
    p = tmp_path / "f.jsonl"
    name = write_jsonl_lines_capped(p, ['{"a":1}\n', '{"b":2}\n'], max_bytes=10_000)
    assert name == "f.jsonl"
    assert p.read_text(encoding="utf-8").count("\n") == 2


def test_jsonl_shards_when_over_cap(tmp_path: Path) -> None:
    p = tmp_path / "f.jsonl"
    lines = [json.dumps({"i": i}) + "\n" for i in range(20)]
    name = write_jsonl_lines_capped(p, lines, max_bytes=80)
    assert name == "f_index.json"
    idx = json.loads((tmp_path / "f_index.json").read_text(encoding="utf-8"))
    assert len(idx["parts"]) >= 2
    for part in idx["parts"]:
        assert (tmp_path / part).stat().st_size <= 80 + 50  # cap + small slack


def test_jsonl_models_capped(tmp_path: Path) -> None:
    p = tmp_path / "m.jsonl"
    models = [_M(x=i) for i in range(30)]
    name = write_jsonl_models_capped(p, models, max_bytes=120)
    assert name == "m_index.json"
