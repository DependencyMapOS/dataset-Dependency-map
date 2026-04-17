from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass
from typing import Literal

from repo_analysis.models.manifest_run import RunManifest

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class JobRecord:
    job_id: str
    status: JobStatus = "queued"
    message: str = ""
    result: RunManifest | None = None


class JobStore:
    """In-memory job queue (single-node; lost on restart)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, JobRecord] = {}

    def create(self) -> str:
        jid = str(uuid.uuid4())
        with self._lock:
            self._jobs[jid] = JobRecord(job_id=jid, status="queued")
        return jid

    def update(self, job_id: str, **kwargs: object) -> None:
        with self._lock:
            rec = self._jobs.get(job_id)
            if rec is None:
                return
            for k, v in kwargs.items():
                setattr(rec, k, v)

    def get(self, job_id: str) -> JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)


job_store = JobStore()
