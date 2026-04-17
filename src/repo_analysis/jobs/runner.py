from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from repo_analysis.config import Settings, get_settings
from repo_analysis.discovery.language_detect import detect_language
from repo_analysis.discovery.walk import iter_source_files
from repo_analysis.export import json_export, split_combined
from repo_analysis.export.gcb_serializer import write_gcb_triples_capped
from repo_analysis.export.node_json_partition import DATASET_MAX_FILE_BYTES
from repo_analysis.export.schema_version import GENERATION_VERSION
from repo_analysis.extraction.function_extractor import extract_repo_functions
from repo_analysis.graph_build.asg_builder import build_asg_for_tree
from repo_analysis.graph_build.ast_builder import build_ast_for_tree
from repo_analysis.graph_build.combine import combine_asg_files, combine_ast_files
from repo_analysis.intake.clone import clone_repo, read_head_commit
from repo_analysis.manifests.collect import collect_manifests, manifest_graph_to_status
from repo_analysis.models.asg import AsgFileArtifact
from repo_analysis.models.ast import AstFileArtifact
from repo_analysis.models.manifest_run import DatasetIndexEntry, RunArtifacts, RunManifest
from repo_analysis.models.warnings import WarningEnvelope, WarningRecord
from repo_analysis.parsing.backends.tree_sitter_backend import TreeSitterBackend
from repo_analysis.persistence.index import append_index
from repo_analysis.persistence.layout import run_root
from repo_analysis.persistence.writer import atomic_write_json, write_jsonl_models_capped
from repo_analysis.resolution.workspace import infer_repo_name


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def run_analysis(
    *,
    url: str,
    branch: str,
    run_id: str | None = None,
    settings: Settings | None = None,
    repository_name: str | None = None,
) -> RunManifest:
    settings = settings or get_settings()
    dataset_root = settings.resolved_dataset_root()
    tool_root = settings.resolved_tool_root()
    run_id = run_id or str(uuid.uuid4())
    started = time.perf_counter()

    from repo_analysis.sandbox.manager import create_sandbox

    sandbox = create_sandbox(settings.sandbox_root)
    clone_dir = sandbox.path / "target"
    warnings: list[dict[str, object]] = []

    try:
        clone_repo(url=url, dest=clone_dir, branch=branch, shallow=True)
        commit_sha = read_head_commit(clone_dir)
        repo_name = infer_repo_name(clone_dir)
        if repository_name is not None:
            stripped = repository_name.strip()
            if stripped:
                repo_name = stripped
        out_dir = run_root(dataset_root, repo_name, branch, commit_sha)
        out_dir.mkdir(parents=True, exist_ok=True)

        manifests = collect_manifests(clone_dir)
        dep_status = manifest_graph_to_status(manifests)

        ast_dir = out_dir / "ast"
        asg_dir = out_dir / "asg"
        meta_dir = out_dir / "metadata"
        ast_dir.mkdir(parents=True, exist_ok=True)
        asg_dir.mkdir(parents=True, exist_ok=True)
        meta_dir.mkdir(parents=True, exist_ok=True)

        ast_files: list[AstFileArtifact] = []
        asg_files: list[AsgFileArtifact] = []
        file_counts: dict[str, int] = {}

        ignore_globs = settings.ignore_globs
        for file_path in iter_source_files(clone_dir, ignore_globs=ignore_globs):
            lang = detect_language(file_path)
            if lang is None:
                continue
            file_counts[lang] = file_counts.get(lang, 0) + 1
            rel = file_path.relative_to(clone_dir).as_posix()
            try:
                source = file_path.read_bytes()
            except OSError as e:
                warnings.append({"code": "read_error", "message": str(e), "path": rel})
                continue
            try:
                backend = TreeSitterBackend(lang)
                pr = backend.parse_file(file_path, source)
            except Exception as e:  # noqa: BLE001
                warnings.append({"code": "parse_init_error", "message": str(e), "path": rel})
                continue

            tree = pr.tree
            ast_res = build_ast_for_tree(
                commit_sha=commit_sha,
                relative_path=rel,
                root=tree.root_node,
                source=source,
            )
            asg_res = build_asg_for_tree(
                commit_sha=commit_sha,
                relative_path=rel,
                language=lang,
                root=tree.root_node,
                source=source,
            )

            ast_art = AstFileArtifact(
                repository_name=repo_name,
                repository_url=url,
                branch=branch,
                commit_sha=commit_sha,
                analysis_timestamp=_iso_now(),
                source_language=lang,
                relative_path=rel,
                parser_id=pr.parser_id,
                generation_version=GENERATION_VERSION,
                dependency_resolution_status=dep_status,
                warnings=[],
                errors=[],
                nodes=ast_res.nodes,
                edges=ast_res.edges,
            )
            asg_art = AsgFileArtifact(
                repository_name=repo_name,
                repository_url=url,
                branch=branch,
                commit_sha=commit_sha,
                analysis_timestamp=_iso_now(),
                source_language=lang,
                relative_path=rel,
                parser_id=pr.parser_id,
                generation_version=GENERATION_VERSION,
                dependency_resolution_status=dep_status,
                warnings=[],
                errors=[],
                nodes=asg_res.nodes,
                edges=asg_res.edges,
            )
            ast_files.append(ast_art)
            asg_files.append(asg_art)
            stem = rel.replace("/", "_")
            json_export.write_json_capped(
                ast_dir / "per-file" / f"{stem}.json",
                ast_art,
                max_bytes=DATASET_MAX_FILE_BYTES,
                graph_kind="ast",
            )
            json_export.write_json_capped(
                asg_dir / "per-file" / f"{stem}.json",
                asg_art,
                max_bytes=DATASET_MAX_FILE_BYTES,
                graph_kind="asg",
            )

        if not ast_files:
            warnings.append({"code": "no_parsable_files", "message": "No supported source files found."})

        combined_ast = combine_ast_files(ast_files) if ast_files else None
        combined_asg = combine_asg_files(asg_files) if asg_files else None
        if combined_ast is not None:
            split_combined.write_split_combined_json_and_graphml(
                model=combined_ast,
                out_dir=ast_dir,
                graph_kind="ast",
                commit_sha=commit_sha,
                tool_version=GENERATION_VERSION,
                max_bytes=DATASET_MAX_FILE_BYTES,
            )
        if combined_asg is not None:
            split_combined.write_split_combined_json_and_graphml(
                model=combined_asg,
                out_dir=asg_dir,
                graph_kind="asg",
                commit_sha=commit_sha,
                tool_version=GENERATION_VERSION,
                max_bytes=DATASET_MAX_FILE_BYTES,
            )

        # Function extraction + GCB (after ASG artifacts are prepared)
        func_files: list[tuple[str, bytes, str]] = []
        for file_path in iter_source_files(clone_dir, ignore_globs=ignore_globs):
            lang = detect_language(file_path)
            if lang is None:
                continue
            rel = file_path.relative_to(clone_dir).as_posix()
            try:
                src = file_path.read_bytes()
            except OSError:
                continue
            func_files.append((rel, src, lang))

        functions = extract_repo_functions(
            repo_root_name=repo_name,
            commit_sha=commit_sha,
            files=func_files,
        )
        functions_rel = write_jsonl_models_capped(
            out_dir / "functions.jsonl", functions, DATASET_MAX_FILE_BYTES
        )
        gcb_rel = write_gcb_triples_capped(
            out_dir / "gcb_triples.jsonl", functions, DATASET_MAX_FILE_BYTES
        )

        warn_models: list[WarningRecord] = []
        for w in warnings:
            p = w.get("path")
            ln = w.get("line")
            warn_models.append(
                WarningRecord(
                    code=str(w.get("code", "warning")),
                    message=str(w.get("message", "")),
                    path=p if isinstance(p, str) else None,
                    line=ln if isinstance(ln, int) else None,
                )
            )
        atomic_write_json(meta_dir / "warnings.json", WarningEnvelope(warnings=warn_models).model_dump())

        atomic_write_json(
            meta_dir / "config_snapshot.json",
            {
                "tool_root": str(tool_root),
                "dataset_root": str(dataset_root),
                "ignore_globs": list(settings.ignore_globs),
            },
        )
        atomic_write_json(
            meta_dir / "repo_summary.json",
            {"repository_url": url, "branch": branch, "commit_sha": commit_sha},
        )
        atomic_write_json(
            meta_dir / "language_summary.json",
            file_counts,
        )

        duration = time.perf_counter() - started
        manifest = RunManifest(
            run_id=run_id,
            repository_url=url,
            repository_name=repo_name,
            branch=branch,
            commit_sha=commit_sha,
            analysis_timestamp=_iso_now(),
            tool_version=GENERATION_VERSION,
            dependency_resolution_status=dep_status,
            output_root=(
                str(out_dir.relative_to(dataset_root))
                if out_dir.is_relative_to(dataset_root)
                else str(out_dir)
            ),
            duration_seconds=duration,
            file_counts_by_language=file_counts,
            artifacts=RunArtifacts(
                ast_dir=str(ast_dir.relative_to(out_dir)),
                asg_dir=str(asg_dir.relative_to(out_dir)),
                functions_jsonl=functions_rel,
                gcb_triples_jsonl=gcb_rel,
            ),
            artifacts_paths=[
                str(ast_dir.relative_to(out_dir)),
                str(asg_dir.relative_to(out_dir)),
                functions_rel,
                gcb_rel,
            ],
        )
        atomic_write_json(meta_dir / "run_manifest.json", manifest.model_dump())

        append_index(
            dataset_root,
            DatasetIndexEntry(
                run_id=run_id,
                repo=repo_name,
                branch=branch,
                commit=commit_sha,
                timestamp=_iso_now(),
                path=str(out_dir.relative_to(dataset_root)),
            ),
        )
        return manifest
    finally:
        sandbox.cleanup()
