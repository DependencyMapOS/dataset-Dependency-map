from __future__ import annotations

from pydantic import BaseModel, Field


class WarningRecord(BaseModel):
    """Structured warning attached to artifacts or runs."""

    code: str
    message: str
    path: str | None = None
    line: int | None = None


class ErrorRecord(BaseModel):
    """Hard failure on a file or step."""

    code: str
    message: str
    path: str | None = None
    line: int | None = None


class WarningEnvelope(BaseModel):
    """Aggregated warnings file."""

    warnings: list[WarningRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)
