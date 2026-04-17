from __future__ import annotations

from repo_analysis.intake.git_remote import repo_display_name_from_url


def test_repo_display_name_from_url_last_segment() -> None:
    assert repo_display_name_from_url("https://github.com/org/my-repo") == "my-repo"
    assert repo_display_name_from_url("https://github.com/org/my-repo/") == "my-repo"


def test_repo_display_name_from_url_strips_git_suffix() -> None:
    assert repo_display_name_from_url("https://github.com/org/my-repo.git") == "my-repo"
