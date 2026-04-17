from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

from repo_analysis.config import get_settings
from repo_analysis.export.gcb_serializer import serialize_run_to_path
from repo_analysis.intake.git_remote import list_remote_branches, repo_display_name_from_url
from repo_analysis.jobs.runner import run_analysis
from repo_analysis.log import configure_logging
from repo_analysis.models.asg import AsgCombinedArtifact
from repo_analysis.models.ast import AstCombinedArtifact
from repo_analysis.models.manifest_run import DatasetIndex
from repo_analysis.persistence.writer import atomic_write_json

app = typer.Typer(add_completion=False, no_args_is_help=True)


@app.command("branches")
def branches_cmd(
    url: str,
    as_json: Annotated[bool, typer.Option("--json", help="Machine-readable JSON")] = False,
) -> None:
    """List remote branches for a public Git URL."""
    names = list_remote_branches(url)
    if as_json:
        typer.echo(json.dumps({"branches": names}))
    else:
        for b in names:
            typer.echo(b)


@app.command("analyze")
def analyze_cmd(
    url: str = typer.Option(..., "--url", help="Git repository URL"),
    branch: str = typer.Option(..., "--branch", help="Branch to analyze"),
    repo_name: str | None = typer.Option(
        None,
        "--repo-name",
        help="Name for dataset paths and artifacts (default: clone directory name, often 'target')",
    ),
    output_root: Path | None = typer.Option(None, "--output-root", help="Dataset root"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """Run full analysis pipeline."""
    configure_logging(verbose=verbose)
    settings = get_settings()
    if output_root is not None:
        settings.dataset_root = output_root
    run_id = str(uuid.uuid4())
    manifest = run_analysis(
        url=url,
        branch=branch,
        run_id=run_id,
        settings=settings,
        repository_name=repo_name,
    )
    typer.echo(json.dumps(manifest.model_dump(), indent=2))


def _read_repo_urls_from_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    urls: list[str] = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        urls.append(line)
    return urls


@app.command("batch-from-list")
def batch_from_list_cmd(
    list_file: Path = typer.Argument(..., help="Text file: one Git URL per line (# comments allowed)"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="List branches only; do not run analysis")] = False,
    continue_on_error: Annotated[
        bool,
        typer.Option("--continue-on-error", help="Continue after a failed repo or branch"),
    ] = False,
    output_root: Path | None = typer.Option(None, "--output-root", help="Dataset root"),
    verbose: bool = typer.Option(False, "--verbose"),
) -> None:
    """For each repo URL: discover remote branches, then analyze every branch (repo name = last URL path segment)."""
    configure_logging(verbose=verbose)
    settings = get_settings()
    if output_root is not None:
        settings.dataset_root = output_root

    urls = _read_repo_urls_from_file(list_file)
    if not urls:
        typer.echo("No repository URLs found in the file (empty or only comments).", err=True)
        raise typer.Exit(code=1)

    failures: list[str] = []
    runs = 0
    for url in urls:
        repo_name = repo_display_name_from_url(url)
        try:
            branches = list_remote_branches(url)
        except Exception as e:
            msg = f"{url}: list branches failed: {e}"
            typer.echo(msg, err=True)
            failures.append(msg)
            if not continue_on_error:
                raise typer.Exit(code=1) from e
            continue

        preview = ", ".join(branches[:8])
        extra = f" … (+{len(branches) - 8} more)" if len(branches) > 8 else ""
        typer.echo(f"[{repo_name}] {len(branches)} branch(es): {preview}{extra}")

        for branch in branches:
            runs += 1
            label = f"{repo_name} @ {branch}"
            if dry_run:
                typer.echo(f"  dry-run: {url} --branch {branch} --repo-name {repo_name}")
                continue
            run_id = str(uuid.uuid4())
            try:
                manifest = run_analysis(
                    url=url,
                    branch=branch,
                    run_id=run_id,
                    settings=settings,
                    repository_name=repo_name,
                )
                typer.echo(f"  ok {label} -> {manifest.output_root}")
            except Exception as e:
                msg = f"{label}: {e}"
                typer.echo(f"  FAIL {msg}", err=True)
                failures.append(msg)
                if not continue_on_error:
                    raise typer.Exit(code=1) from e

    if dry_run:
        typer.echo(f"Dry run finished: {runs} branch(es) across {len(urls)} repo(s).")
    else:
        typer.echo(f"Finished {runs} analysis run(s); {len(failures)} failure(s).")

    if failures:
        raise typer.Exit(code=1)


@app.command("validate")
def validate_cmd(run_dir: Path) -> None:
    """Validate JSON artifacts in a run directory."""
    errors: list[str] = []
    meta = run_dir / "metadata"
    for name in ("run_manifest.json",):
        p = meta / name
        if not p.exists():
            errors.append(f"missing {p}")
    def _validate_sharded_or_legacy(combined_dir: Path, model_cls: type[BaseModel]) -> None:
        idx = combined_dir / "combined_index.json"
        legacy = combined_dir / "combined.json"
        if idx.exists():
            data = json.loads(idx.read_text(encoding="utf-8"))
            for part in data.get("parts", []):
                jp = combined_dir / part["json"]
                if not jp.exists():
                    errors.append(f"missing {jp}")
                    continue
                model_cls.model_validate_json(jp.read_text(encoding="utf-8"))
                gml = combined_dir / part["graphml"]
                if gml.exists():
                    try:
                        ET.parse(gml)
                    except ET.ParseError as e:
                        errors.append(f"GraphML parse {gml}: {e}")
        elif legacy.exists():
            model_cls.model_validate_json(legacy.read_text(encoding="utf-8"))
            gml = combined_dir / "combined.graphml"
            if gml.exists():
                try:
                    ET.parse(gml)
                except ET.ParseError as e:
                    errors.append(f"GraphML parse {gml}: {e}")

    _validate_sharded_or_legacy(run_dir / "ast", AstCombinedArtifact)
    _validate_sharded_or_legacy(run_dir / "asg", AsgCombinedArtifact)
    if errors:
        typer.echo("\n".join(errors), err=True)
        raise typer.Exit(code=1)
    typer.echo("ok")


@app.command("datasets")
def datasets_cmd(
    action: Annotated[str, typer.Argument(help="list")],
) -> None:
    """Inspect dataset index."""
    if action != "list":
        raise typer.BadParameter("only 'list' is supported")
    settings = get_settings()
    idx_path = settings.resolved_dataset_root() / "index.json"
    if not idx_path.exists():
        typer.echo(json.dumps({"entries": []}))
        return
    idx = DatasetIndex.model_validate_json(idx_path.read_text(encoding="utf-8"))
    typer.echo(json.dumps({"entries": [e.model_dump() for e in idx.entries]}, indent=2))


@app.command("gcb-export")
def gcb_export_cmd(run_dir: Path) -> None:
    """Re-run GraphCodeBERT serialization from a completed run."""
    fn = run_dir / "functions.jsonl"
    fidx = run_dir / "functions_index.json"
    if not fn.exists() and not fidx.exists():
        typer.echo(f"missing {fn} or {fidx}", err=True)
        raise typer.Exit(code=1)
    out = run_dir / "gcb_triples.jsonl"
    written = serialize_run_to_path(run_dir=run_dir, output_jsonl=out)
    manifest_path = run_dir / "metadata" / "run_manifest.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        arts = data.get("artifacts") or {}
        arts["gcb_triples_jsonl"] = written
        data["artifacts"] = arts
        atomic_write_json(manifest_path, data)
    typer.echo(str(run_dir / written))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
