# Setup

This document describes how to set up the **repo-analysis** backend on your machine.

## Prerequisites

- **Python 3.11+** (3.12 is fine)
- **Git** on your `PATH` (used for `git clone` and `git ls-remote`)
- A terminal where `python` and `pip` work

## 1. Clone and enter the repository

```powershell
cd "c:\path\to\dataset-Dependency-map"
```

Use your actual clone path if different.

## 2. Create and activate a virtual environment

**Windows (PowerShell):**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**macOS / Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3. Install the package and dev dependencies

```powershell
python -m pip install --upgrade pip
pip install -e ".[dev]"
```

This installs the `repo_analysis` package in editable mode, the `repo-analyze` console script (when Scripts is on `PATH`), FastAPI, tree-sitter, pytest, Ruff, mypy, and other dev tools.

If `repo-analyze` is not found, call the CLI with:

```powershell
python -m repo_analysis --help
```

## 4. Output location (`dataset/`)

Analysis writes under **`dataset/`** in the tool repository. The tool resolves the project root from the current working directory or from the environment variable **`ANALYSIS_TOOL_ROOT`**.

If you run commands from outside the repo, set the root explicitly:

**PowerShell:**

```powershell
$env:ANALYSIS_TOOL_ROOT = "c:\path\to\dataset-Dependency-map"
```

## 5. Verify the install

```powershell
python -m pytest -q
python -c "from repo_analysis.api.app import create_app; print(create_app().title)"
```

You should see `repo-analysis` printed and tests passing (if you ran pytest).

## 6. Run the CLI

The package includes `src/repo_analysis/__main__.py`, so **`python -m repo_analysis`** works the same as the **`repo-analyze`** entry point when your `Scripts` folder is on `PATH`.

Example (requires network and a public Git URL):

```powershell
python -m repo_analysis branches https://github.com/octocat/Hello-World --json
```

Full analysis:

```powershell
python -m repo_analysis analyze --url https://github.com/org/repo --branch main
```

Other commands: `validate`, `datasets list`, `gcb-export` — see `README.md`.

## 7. Run the REST API

```powershell
uvicorn repo_analysis.api.app:app --reload --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/docs` for the interactive OpenAPI UI.

## Optional: quality checks

```powershell
ruff check src tests
mypy src
```

---

For a short overview of commands and API routes, see [`README.md`](README.md).
