from __future__ import annotations

import json
from pathlib import Path

from repo_analysis.export.gcb_serializer import function_to_triple, write_gcb_triples
from repo_analysis.models.function_record import FunctionRecord, FunctionSpan, SourcePoint


def test_truncation_flag() -> None:
    sig = ["def", "f", "(", "):"]
    body = ["x"] * 600
    rec = FunctionRecord(
        id="r:p::f:0",
        signature_tokens=sig,
        body_tokens=body,
        docstring=None,
        span=FunctionSpan(
            start=SourcePoint(line=1, col=0),
            end=SourcePoint(line=2, col=0),
        ),
        module_path="m.py",
        language="python",
    )
    triple = function_to_triple(rec)
    assert triple.truncated is True
    assert len(triple.code_tokens) + len(triple.nl_tokens) <= 512


def test_empty_docstring_nl_tokens() -> None:
    rec = FunctionRecord(
        id="r:p::f:0",
        signature_tokens=["def", "f", "():"],
        body_tokens=["pass"],
        docstring=None,
        span=FunctionSpan(
            start=SourcePoint(line=1, col=0),
            end=SourcePoint(line=2, col=0),
        ),
        module_path="m.py",
        language="python",
    )
    triple = function_to_triple(rec)
    assert triple.nl_tokens == []


def test_jsonlines_roundtrip(tmp_path: Path) -> None:
    rec = FunctionRecord(
        id="r:p::f:0",
        signature_tokens=["def", "f", "():"],
        body_tokens=["return", "1"],
        docstring="hello",
        span=FunctionSpan(
            start=SourcePoint(line=1, col=0),
            end=SourcePoint(line=2, col=0),
        ),
        module_path="m.py",
        language="python",
    )
    out = tmp_path / "out.jsonl"
    write_gcb_triples(out, [rec])
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["id"] == rec.id
    assert "code_tokens" in data and "nl_tokens" in data and "dfg" in data
