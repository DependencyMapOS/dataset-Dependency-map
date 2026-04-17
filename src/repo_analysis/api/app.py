from __future__ import annotations

from fastapi import FastAPI

from repo_analysis import __version__
from repo_analysis.api.routes import datasets, jobs, repos


def create_app() -> FastAPI:
    app = FastAPI(title="repo-analysis", version=__version__)
    app.include_router(repos.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(datasets.router, prefix="/api/v1")
    return app


app = create_app()
