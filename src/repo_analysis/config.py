from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_IGNORE_GLOBS: tuple[str, ...] = (
    ".git/**",
    "**/node_modules/**",
    "**/dist/**",
    "**/build/**",
    "**/.venv/**",
    "**/venv/**",
    "**/target/**",
    "**/bin/**",
    "**/obj/**",
    "**/.cache/**",
)


class Settings(BaseSettings):
    """Runtime configuration (env + optional defaults)."""

    model_config = SettingsConfigDict(env_prefix="ANALYSIS_", env_file=None, extra="ignore")

    tool_root: Path = Field(
        default_factory=lambda: Path.cwd(),
        description="Root of this tool repo (contains pyproject.toml and dataset/).",
    )
    dataset_root: Path | None = Field(
        default=None,
        description="Override for dataset output root; defaults to tool_root/dataset.",
    )
    sandbox_root: Path | None = Field(
        default=None,
        description="Optional parent for temp sandboxes; default system temp.",
    )
    ignore_globs: tuple[str, ...] = Field(default=DEFAULT_IGNORE_GLOBS)

    def resolved_dataset_root(self) -> Path:
        base = self.dataset_root or (self.tool_root / "dataset")
        return base.resolve()

    def resolved_tool_root(self) -> Path:
        return self.tool_root.resolve()


def get_settings() -> Settings:
    return Settings()
