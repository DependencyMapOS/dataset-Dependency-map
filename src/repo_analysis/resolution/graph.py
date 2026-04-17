from __future__ import annotations

from dataclasses import dataclass, field

from repo_analysis.manifests.models import ManifestSnapshot


@dataclass
class StaticDependencyGraph:
    """Edges from manifests only (no registry)."""

    manifests: list[ManifestSnapshot] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def build_static_graph(manifests: list[ManifestSnapshot]) -> StaticDependencyGraph:
    return StaticDependencyGraph(manifests=list(manifests))
