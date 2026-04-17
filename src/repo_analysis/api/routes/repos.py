from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from repo_analysis.intake.git_remote import list_remote_branches

router = APIRouter(tags=["repos"])


@router.get("/repos/branches")
def branches(url: str = Query(..., description="Git remote URL (https)")) -> dict[str, list[str]]:
    try:
        names = list_remote_branches(url)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"branches": names}
