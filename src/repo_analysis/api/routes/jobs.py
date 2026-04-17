from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from repo_analysis.api.deps import settings_dep
from repo_analysis.config import Settings
from repo_analysis.jobs.runner import run_analysis
from repo_analysis.jobs.store import job_store

router = APIRouter(tags=["jobs"])


class JobCreate(BaseModel):
    url: str = Field(..., description="Repository URL")
    branch: str = Field(..., description="Branch name")
    repository_name: str | None = Field(
        None,
        description="Optional name for dataset paths and artifacts (default: clone directory name)",
    )


def _run_job(job_id: str, url: str, branch: str, repository_name: str | None) -> None:
    job_store.update(job_id, status="running", message="cloning and analyzing")
    try:
        manifest = run_analysis(
            url=url, branch=branch, run_id=job_id, repository_name=repository_name
        )
        job_store.update(job_id, status="completed", message="done", result=manifest)
    except Exception as e:  # noqa: BLE001
        job_store.update(job_id, status="failed", message=str(e))


@router.post("/jobs")
def create_job(
    body: JobCreate,
    background: BackgroundTasks,
    settings: Settings = Depends(settings_dep),
) -> dict[str, str]:
    _ = settings
    job_id = job_store.create()
    background.add_task(_run_job, job_id, body.url, body.branch, body.repository_name)
    return {"job_id": job_id}


@router.get("/jobs/{job_id}")
def job_status(job_id: str) -> dict[str, str]:
    rec = job_store.get(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown job")
    return {"job_id": job_id, "status": rec.status, "message": rec.message}


@router.get("/jobs/{job_id}/result")
def job_result(job_id: str) -> dict[str, object]:
    rec = job_store.get(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="unknown job")
    if rec.status != "completed" or rec.result is None:
        raise HTTPException(status_code=400, detail="job not completed")
    return {"manifest": rec.result.model_dump()}
