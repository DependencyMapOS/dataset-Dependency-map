from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

from repo_analysis.manifests.models import ManifestSnapshot, PackageRef


def collect_manifests(repo_root: Path) -> list[ManifestSnapshot]:
    """Best-effort manifest discovery (offline, no registry)."""
    found: list[ManifestSnapshot] = []
    for path in sorted(repo_root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(repo_root).as_posix()
        name = path.name.lower()
        if name == "package.json" and "node_modules" not in path.parts:
            found.append(_read_package_json(path, rel))
        elif name == "pyproject.toml":
            found.append(_read_pyproject_toml(path, rel))
        elif name == "requirements.txt":
            found.append(_read_requirements_txt(path, rel))
        elif name == "go.mod":
            found.append(_read_go_mod(path, rel))
        elif name == "cargo.toml":
            found.append(_read_cargo_toml(path, rel))
        elif name == "pom.xml":
            found.append(_read_pom_xml(path, rel))
        elif name.endswith(".csproj"):
            found.append(_read_csproj(path, rel))
    return found


def _read_package_json(path: Path, rel: str) -> ManifestSnapshot:
    data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    pkgs: list[PackageRef] = []
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        block = data.get(section)
        if isinstance(block, dict):
            for k, v in block.items():
                pkgs.append(PackageRef(name=str(k), version_spec=str(v) if v is not None else None))
    return ManifestSnapshot(ecosystem="npm", path=rel, packages=pkgs, raw_keys=list(data.keys()))


def _read_pyproject_toml(path: Path, rel: str) -> ManifestSnapshot:
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    pkgs: list[PackageRef] = []
    project = data.get("project")
    if isinstance(project, dict):
        deps = project.get("dependencies")
        if isinstance(deps, list):
            for d in deps:
                pkgs.append(_split_dep(str(d)))
        opt = project.get("optional-dependencies")
        if isinstance(opt, dict):
            for vals in opt.values():
                if isinstance(vals, list):
                    for d in vals:
                        pkgs.append(_split_dep(str(d)))
    return ManifestSnapshot(ecosystem="python", path=rel, packages=pkgs, raw_keys=list(data.keys()))


def _split_dep(spec: str) -> PackageRef:
    m = re.match(r"([A-Za-z0-9_.-]+)\s*(.*)", spec.strip())
    if not m:
        return PackageRef(name=spec)
    return PackageRef(name=m.group(1), version_spec=m.group(2).strip() or None)


def _read_requirements_txt(path: Path, rel: str) -> ManifestSnapshot:
    pkgs: list[PackageRef] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("-"):
            continue
        pkgs.append(_split_dep(s.split(";", 1)[0]))
    return ManifestSnapshot(ecosystem="pip", path=rel, packages=pkgs, raw_keys=[])


def _read_go_mod(path: Path, rel: str) -> ManifestSnapshot:
    pkgs: list[PackageRef] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("require "):
            rest = s[len("require ") :].strip()
            if rest.startswith("("):
                continue
            parts = rest.split()
            if len(parts) >= 1:
                pkgs.append(PackageRef(name=parts[0], version_spec=parts[1] if len(parts) > 1 else None))
        elif s.startswith("require ("):
            continue
        elif s.endswith(")") and not s.startswith("require"):
            continue
        elif s and not s.startswith(("module ", "go ", "replace ", "exclude ", "retract ", ")")):
            parts = s.split()
            if len(parts) >= 1 and "/" in parts[0]:
                pkgs.append(PackageRef(name=parts[0], version_spec=parts[1] if len(parts) > 1 else None))
    return ManifestSnapshot(ecosystem="go", path=rel, packages=pkgs, raw_keys=[])


def _read_cargo_toml(path: Path, rel: str) -> ManifestSnapshot:
    data = tomllib.loads(path.read_text(encoding="utf-8", errors="replace"))
    pkgs: list[PackageRef] = []
    deps = data.get("dependencies")
    if isinstance(deps, dict):
        for k, v in deps.items():
            if isinstance(v, str):
                pkgs.append(PackageRef(name=str(k), version_spec=v))
            elif isinstance(v, dict):
                pkgs.append(
                    PackageRef(
                        name=str(k),
                        version_spec=str(v.get("version")) if v.get("version") is not None else None,
                    )
                )
    return ManifestSnapshot(ecosystem="rust", path=rel, packages=pkgs, raw_keys=list(data.keys()))


def _read_pom_xml(path: Path, rel: str) -> ManifestSnapshot:
    text = path.read_text(encoding="utf-8", errors="replace")
    pkgs: list[PackageRef] = []
    for m in re.finditer(
        r"<dependency>\s*<groupId>([^<]+)</groupId>\s*<artifactId>([^<]+)</artifactId>",
        text,
        re.DOTALL,
    ):
        pkgs.append(PackageRef(name=f"{m.group(1)}:{m.group(2)}", version_spec=None))
    return ManifestSnapshot(ecosystem="maven", path=rel, packages=pkgs, raw_keys=[])


def _read_csproj(path: Path, rel: str) -> ManifestSnapshot:
    text = path.read_text(encoding="utf-8", errors="replace")
    pkgs: list[PackageRef] = []
    for m in re.finditer(
        r'<PackageReference\s+Include="([^"]+)"(?:\s+Version="([^"]+)")?',
        text,
    ):
        pkgs.append(PackageRef(name=m.group(1), version_spec=m.group(2)))
    return ManifestSnapshot(ecosystem="nuget", path=rel, packages=pkgs, raw_keys=[])


def manifest_graph_to_status(manifests: list[ManifestSnapshot]) -> str:
    """Return dependency_resolution_status string for offline static policy."""
    if not manifests:
        return "unresolved"
    return "manifest_only"
