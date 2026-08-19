"""PF-014 GitHub Actions API evidence tests."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from release.github_actions_evidence import (
    GitHubActionsEvidenceError,
    build_github_actions_evidence,
)

_RELEASE_COMMIT = "a" * 40
_VERIFIED_AT = datetime(2026, 8, 19, tzinfo=UTC)


def _run() -> dict[str, Any]:
    return {
        "id": 123,
        "run_attempt": 2,
        "html_url": "https://github.com/skgur07/Koguard/actions/runs/123",
        "head_sha": _RELEASE_COMMIT,
        "event": "push",
        "conclusion": "success",
        "name": "CI",
        "repository": {"full_name": "skgur07/Koguard"},
    }


def _jobs() -> dict[str, Any]:
    return {
        "jobs": [
            {
                "id": 1,
                "name": "ubuntu-latest / CPython 3.11.9",
                "conclusion": "success",
            },
            {
                "id": 2,
                "name": "windows-latest / CPython 3.11.9",
                "conclusion": "success",
            },
            {
                "id": 3,
                "name": "macos-latest / CPython 3.11.9",
                "conclusion": "success",
            },
            {
                "id": 4,
                "name": "Verify reproducible release artifact",
                "conclusion": "success",
            },
        ]
    }


def test_build_github_actions_evidence_uses_successful_api_payload() -> None:
    evidence = build_github_actions_evidence(
        _run(),
        _jobs(),
        expected_commit=_RELEASE_COMMIT,
        verified_at=_VERIFIED_AT,
    )

    assert evidence["provider"] == "github-actions"
    assert evidence["head_sha"] == _RELEASE_COMMIT
    assert [job["runner"] for job in evidence["jobs"]] == [
        "ubuntu-latest",
        "windows-latest",
        "macos-latest",
        "release-artifact",
    ]


def test_build_github_actions_evidence_rejects_stale_or_incomplete_run() -> None:
    run = _run()
    run["head_sha"] = "b" * 40

    with pytest.raises(GitHubActionsEvidenceError, match="commit"):
        build_github_actions_evidence(
            run,
            _jobs(),
            expected_commit=_RELEASE_COMMIT,
            verified_at=_VERIFIED_AT,
        )

    jobs = _jobs()
    jobs["jobs"] = jobs["jobs"][:-1]
    with pytest.raises(GitHubActionsEvidenceError, match="required jobs"):
        build_github_actions_evidence(
            _run(),
            jobs,
            expected_commit=_RELEASE_COMMIT,
            verified_at=_VERIFIED_AT,
        )
