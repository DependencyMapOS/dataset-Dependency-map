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
from repo_analysis.intake.git_remote import list_remote_branches
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
    if not fn.exists():
        typer.echo(f"missing {fn}", err=True)
        raise typer.Exit(code=1)
    out = run_dir / "gcb_triples.jsonl"
    serialize_run_to_path(functions_jsonl=fn, output_jsonl=out)
    # refresh manifest paths if present
    manifest_path = run_dir / "metadata" / "run_manifest.json"
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
        arts = data.get("artifacts") or {}
        arts["gcb_triples_jsonl"] = "gcb_triples.jsonl"
        data["artifacts"] = arts
        atomic_write_json(manifest_path, data)
    typer.echo(str(out))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
