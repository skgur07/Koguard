"""Fetch and sanitize GitHub Actions API evidence for a Koguard release commit."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

_REPOSITORY = "skgur07/Koguard"
_WORKFLOW = "CI"
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_RUN_URL_PATTERN = re.compile(r"^https://github\.com/skgur07/Koguard/actions/runs/([1-9][0-9]*)$")
_REQUIRED_JOBS: tuple[tuple[str, str], ...] = (
    ("ubuntu-latest", "ubuntu-latest / CPython 3.11.9"),
    ("windows-latest", "windows-latest / CPython 3.11.9"),
    ("macos-latest", "macos-latest / CPython 3.11.9"),
)


class GitHubActionsEvidenceError(ValueError):
    """Raised when a GitHub Actions run cannot prove the release CI gate."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubActionsEvidenceError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _positive_integer(value: object, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise GitHubActionsEvidenceError(f"{label} must be a positive integer")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise GitHubActionsEvidenceError(f"{label} must be a non-empty string")
    return value


def build_github_actions_evidence(
    run_payload: Mapping[str, Any],
    jobs_payload: Mapping[str, Any],
    *,
    expected_commit: str,
    verified_at: datetime | None = None,
) -> dict[str, Any]:
    """Validate GitHub API payloads and return closed release CI evidence."""

    if _COMMIT_PATTERN.fullmatch(expected_commit) is None:
        raise GitHubActionsEvidenceError("expected release commit must be a full Git SHA")
    timestamp = verified_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise GitHubActionsEvidenceError("verified_at must include timezone information")

    run_id = _positive_integer(run_payload.get("id"), "run.id")
    run_attempt = _positive_integer(run_payload.get("run_attempt"), "run.run_attempt")
    run_url = _string(run_payload.get("html_url"), "run.html_url")
    match = _RUN_URL_PATTERN.fullmatch(run_url)
    if match is None or int(match.group(1)) != run_id:
        raise GitHubActionsEvidenceError("run URL and run id do not match Koguard")
    repository = _object(run_payload.get("repository"), "run.repository")
    if repository.get("full_name") != _REPOSITORY:
        raise GitHubActionsEvidenceError("run repository is not Koguard")
    if run_payload.get("name") != _WORKFLOW:
        raise GitHubActionsEvidenceError("run workflow is not CI")
    if run_payload.get("head_sha") != expected_commit:
        raise GitHubActionsEvidenceError("run does not match the expected release commit")
    if run_payload.get("event") not in {"push", "workflow_dispatch"}:
        raise GitHubActionsEvidenceError("run event is not an approved release trigger")
    if run_payload.get("conclusion") != "success":
        raise GitHubActionsEvidenceError("run conclusion must be success")

    raw_jobs = jobs_payload.get("jobs")
    if not isinstance(raw_jobs, list):
        raise GitHubActionsEvidenceError("jobs payload must contain an array")
    jobs_by_name: dict[str, dict[str, Any]] = {}
    for raw_job in raw_jobs:
        job = _object(raw_job, "job")
        name = job.get("name")
        if isinstance(name, str) and name in jobs_by_name:
            raise GitHubActionsEvidenceError(f"duplicate required job name: {name}")
        if isinstance(name, str):
            jobs_by_name[name] = job

    missing = [name for _, name in _REQUIRED_JOBS if name not in jobs_by_name]
    if missing:
        raise GitHubActionsEvidenceError(f"required jobs are missing: {missing}")
    jobs: list[dict[str, Any]] = []
    for runner, name in _REQUIRED_JOBS:
        job = jobs_by_name[name]
        if job.get("conclusion") != "success":
            raise GitHubActionsEvidenceError(f"required job did not succeed: {name}")
        jobs.append(
            {
                "job_id": _positive_integer(job.get("id"), f"{name}.id"),
                "name": name,
                "runner": runner,
                "conclusion": "success",
            }
        )

    return {
        "schema_version": 1,
        "provider": "github-actions",
        "repository": _REPOSITORY,
        "workflow": _WORKFLOW,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "run_url": run_url,
        "head_sha": expected_commit,
        "event": run_payload["event"],
        "conclusion": "success",
        "verified_at": timestamp.astimezone(UTC).isoformat(),
        "jobs": jobs,
    }


def _fetch_json(url: str, token: str | None) -> dict[str, Any]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "koguard-release-evidence/0.1.0",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload: object = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise GitHubActionsEvidenceError(f"failed to fetch GitHub Actions evidence: {url}") from exc
    return _object(payload, "GitHub API response")


def fetch_github_actions_evidence(
    run_url: str,
    *,
    expected_commit: str,
    token: str | None = None,
) -> dict[str, Any]:
    """Query GitHub's API and return verified evidence for one public CI run."""

    match = _RUN_URL_PATTERN.fullmatch(run_url)
    if match is None:
        raise GitHubActionsEvidenceError("run_url must identify a Koguard Actions run")
    run_id = match.group(1)
    api_root = f"https://api.github.com/repos/{_REPOSITORY}/actions/runs/{run_id}"
    run_payload = _fetch_json(api_root, token)
    jobs_payload = _fetch_json(f"{api_root}/jobs?per_page=100", token)
    return build_github_actions_evidence(
        run_payload,
        jobs_payload,
        expected_commit=expected_commit,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-url", required=True)
    parser.add_argument("--expected-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Fetch one actual Actions run and write closed CI evidence."""

    arguments = _parser().parse_args(argv)
    try:
        evidence = fetch_github_actions_evidence(
            arguments.run_url,
            expected_commit=arguments.expected_commit,
            token=os.environ.get("GITHUB_TOKEN"),
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"verified GitHub Actions run {evidence['run_id']} for {evidence['head_sha']}")
    except GitHubActionsEvidenceError as exc:
        print(f"GitHub Actions evidence failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
