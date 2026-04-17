from __future__ import annotations

from repo_analysis.models.asg import AsgCombinedArtifact, AsgEdge, AsgFileArtifact, AsgNode
from repo_analysis.models.ast import AstCombinedArtifact, AstEdge, AstFileArtifact, AstNode


def combine_ast_files(files: list[AstFileArtifact]) -> AstCombinedArtifact:
    if not files:
        raise ValueError("no AST files")
    base = files[0]
    nodes: list[AstNode] = []
    edges: list[AstEdge] = []
    warnings: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for f in files:
        nodes.extend(f.nodes)
        edges.extend(f.edges)
        warnings.extend(f.warnings)
        errors.extend(f.errors)
    return AstCombinedArtifact(
        repository_name=base.repository_name,
        repository_url=base.repository_url,
        branch=base.branch,
        commit_sha=base.commit_sha,
        analysis_timestamp=base.analysis_timestamp,
        source_language="multi",
        relative_path="",
        parser_id=base.parser_id,
        generation_version=base.generation_version,
        dependency_resolution_status=base.dependency_resolution_status,
        warnings=warnings,
        errors=errors,
        nodes=nodes,
        edges=edges,
    )


def combine_asg_files(files: list[AsgFileArtifact]) -> AsgCombinedArtifact:
    if not files:
        raise ValueError("no ASG files")
    base = files[0]
    nodes: list[AsgNode] = []
    edges: list[AsgEdge] = []
    warnings: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    for f in files:
        nodes.extend(f.nodes)
        edges.extend(f.edges)
        warnings.extend(f.warnings)
        errors.extend(f.errors)
    return AsgCombinedArtifact(
        repository_name=base.repository_name,
        repository_url=base.repository_url,
        branch=base.branch,
        commit_sha=base.commit_sha,
        analysis_timestamp=base.analysis_timestamp,
        source_language="multi",
        relative_path="",
        parser_id=base.parser_id,
        generation_version=base.generation_version,
        dependency_resolution_status=base.dependency_resolution_status,
        warnings=warnings,
        errors=errors,
        nodes=nodes,
        edges=edges,
    )
