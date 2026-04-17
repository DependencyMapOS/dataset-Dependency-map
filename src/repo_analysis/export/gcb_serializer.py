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


def serialize_run_to_path(*, functions_jsonl: Path, output_jsonl: Path) -> None:
    records = load_functions_jsonl(functions_jsonl)
    write_gcb_triples(output_jsonl, records)
