from __future__ import annotations

from pydantic import BaseModel, Field


class PackageRef(BaseModel):
    name: str
    version_spec: str | None = None
    source: str | None = None


class ManifestSnapshot(BaseModel):
    """Normalized view of manifests found in a repo."""

    ecosystem: str
    path: str
    packages: list[PackageRef] = Field(default_factory=list)
    raw_keys: list[str] = Field(default_factory=list)
