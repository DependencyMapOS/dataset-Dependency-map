from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from repo_analysis.models.function_record import FunctionRecord


class GcbTriple(BaseModel):
    id: str
    code_tokens: list[str]
    nl_tokens: list[str]
    dfg: list[dict[str, str]]
    truncated: bool = False


def _nl_tokens_from_docstring(doc: str | None) -> list[str]:
    if not doc:
        return []
    return [t for t in doc.split() if t]


def _code_tokens(sig: list[str], body: list[str]) -> list[str]:
    return list(sig) + list(body)


def function_to_triple(rec: FunctionRecord) -> GcbTriple:
    sig = list(rec.signature_tokens)
    body = list(rec.body_tokens)
    nl = _nl_tokens_from_docstring(rec.docstring)
    truncated = False
    while len(sig) + len(body) + len(nl) > 512 and body:
        body.pop()
        truncated = True
    while len(sig) + len(body) + len(nl) > 512 and nl:
        nl.pop()
        truncated = True
    code = _code_tokens(sig, body)
    dfg = [{"var": e.var_name, "def": e.def_node_id, "use": e.use_node_id} for e in rec.dfg_edges]
    return GcbTriple(
        id=rec.id,
        code_tokens=code,
        nl_tokens=nl,
        dfg=dfg,
        truncated=truncated,
    )


def write_gcb_triples(path: Path, records: Iterable[FunctionRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            triple = function_to_triple(rec)
            f.write(json.dumps(triple.model_dump(), sort_keys=True) + "\n")


def write_gcb_triples_capped(path: Path, records: Iterable[FunctionRecord], max_bytes: int) -> str:
    """Returns basename: gcb_triples.jsonl or gcb_triples_index.json."""
    from repo_analysis.persistence.writer import write_jsonl_lines_capped

    lines = [json.dumps(function_to_triple(rec).model_dump(), sort_keys=True) + "\n" for rec in records]
    return write_jsonl_lines_capped(path, lines, max_bytes)


def load_functions_jsonl(path: Path) -> list[FunctionRecord]:
    out: list[FunctionRecord] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data: dict[str, Any] = json.loads(line)
            out.append(FunctionRecord.model_validate(data))
    return out


def load_function_records_from_run_dir(run_dir: Path) -> list[FunctionRecord]:
    idx = run_dir / "functions_index.json"
    if idx.exists():
        data = json.loads(idx.read_text(encoding="utf-8"))
        out: list[FunctionRecord] = []
        for name in data.get("parts", []):
            out.extend(load_functions_jsonl(run_dir / name))
        return out
    single = run_dir / "functions.jsonl"
    if single.exists():
        return load_functions_jsonl(single)
    return []


def serialize_run_to_path(*, run_dir: Path, output_jsonl: Path) -> str:
    from repo_analysis.export.node_json_partition import DATASET_MAX_FILE_BYTES

    records = load_function_records_from_run_dir(run_dir)
    return write_gcb_triples_capped(output_jsonl, records, DATASET_MAX_FILE_BYTES)
