# repo-analysis

Backend-only multi-language repository analysis: clone public Git repos into a per-run sandbox, build AST/ASG via tree-sitter, export JSON/GraphML under `dataset/`, extract `FunctionRecord` data and GraphCodeBERT-style triples, then clean up the sandbox.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

## CLI

```bash
python -m repo_analysis branches https://github.com/org/repo --json
python -m repo_analysis analyze --url https://github.com/org/repo --branch main
python -m repo_analysis validate path\to\dataset\...\run_folder
python -m repo_analysis datasets list
python -m repo_analysis gcb-export path\to\run_folder
```

Console script (if on PATH): `repo-analyze ...`

## REST API

```bash
uvicorn repo_analysis.api.app:app --reload
```

- `GET /api/v1/repos/branches?url=...`
- `POST /api/v1/jobs` body `{"url","branch"}`
- `GET /api/v1/jobs/{id}` / `GET /api/v1/jobs/{id}/result`
- `GET /api/v1/datasets`

Set `ANALYSIS_TOOL_ROOT` or run from the tool repository so outputs land in `./dataset/`.

## Tests

```bash
pytest
ruff check src tests
mypy src
```
