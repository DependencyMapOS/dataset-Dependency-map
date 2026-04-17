from __future__ import annotations


def test_api_app_imports() -> None:
    from repo_analysis.api.app import create_app

    app = create_app()
    assert app.title == "repo-analysis"
