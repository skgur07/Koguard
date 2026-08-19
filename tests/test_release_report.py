"""PF-014 release decision report contract tests."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from release.release_report import (
    RELEASE_REPORT_SCHEMA_PATH,
    TESTPYPI_EVIDENCE_SCHEMA_PATH,
    ReleaseReportError,
    build_release_report,
)

_RELEASE_COMMIT = "a" * 40
_GENERATED_AT = datetime(2026, 8, 19, tzinfo=UTC)


def _artifact_audit() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-19T00:00:00+00:00",
        "environment": {
            "python_version": "3.11.9",
            "implementation": "CPython",
            "platform": "test",
        },
        "package": {
            "name": "koguard",
            "version": "0.1.0",
            "requires_python": ">=3.11,<3.12",
            "license_expression": "MIT",
            "runtime_dependencies": [],
        },
        "artifacts": [
            {
                "kind": "wheel",
                "filename": "koguard-0.1.0-py3-none-any.whl",
                "size_bytes": 40000,
                "sha256": "1" * 64,
            },
            {
                "kind": "sdist",
                "filename": "koguard-0.1.0.tar.gz",
                "size_bytes": 250000,
                "sha256": "2" * 64,
            },
        ],
    }


def _rights_manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(Path("release/rights-manifest.v1.json").read_text(encoding="utf-8")),
    )


def _ci_evidence() -> dict[str, Any]:
    return {
        "status": "passed",
        "head_sha": _RELEASE_COMMIT,
        "run_url": "https://github.com/skgur07/Koguard/actions/runs/1",
        "platforms": ["ubuntu-latest", "windows-latest", "macos-latest"],
    }


def _public_contract() -> dict[str, bool]:
    return {
        "public_api_frozen": True,
        "readme_claims_reviewed": True,
        "limitations_documented": True,
        "core_ai_scope_separated": True,
        "private_vulnerability_reporting_enabled": True,
    }


def _hidden_evaluation() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "report_kind": "hidden-evaluation",
        "release_commit": _RELEASE_COMMIT,
        "evaluation": {
            "attestation_sha256": "3" * 64,
            "approval_count": 2,
            "direct_leak_count": 0,
            "normalized_leak_count": 0,
            "gold_ready": True,
        },
        "source": {
            "protected_ablation_report_sha256": "4" * 64,
            "corpus": {
                "classification": "independent-hidden-evaluation",
                "excluded_review_count": 0,
                "gold_ready": True,
            },
        },
        "balanced_gates": {"passed": True},
    }


def _testpypi_evidence() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "index_url": "https://test.pypi.org/simple/",
        "project_url": "https://test.pypi.org/project/koguard/0.1.0/",
        "package": {"name": "koguard", "version": "0.1.0"},
        "tested_at": "2026-08-19T00:00:00+00:00",
        "python_version": "3.11.9",
        "metadata_verified": True,
        "artifacts": [
            {"kind": "wheel", "sha256": "1" * 64, "smoke_passed": True},
            {"kind": "sdist", "sha256": "2" * 64, "smoke_passed": True},
        ],
    }


def test_release_report_contracts_are_versioned_and_closed() -> None:
    report_schema = json.loads(RELEASE_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))
    testpypi_schema = json.loads(TESTPYPI_EVIDENCE_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["additionalProperties"] is False
    assert testpypi_schema["properties"]["schema_version"]["const"] == 1
    assert testpypi_schema["properties"]["project_url"]["const"] == (
        "https://test.pypi.org/project/koguard/0.1.0/"
    )
    assert testpypi_schema["additionalProperties"] is False


def test_release_report_stays_blocked_until_hidden_and_testpypi_exist() -> None:
    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert report["gates"]["artifacts"] is True
    assert report["gates"]["rights"] is True
    assert report["gates"]["ci"] is True
    assert report["gates"]["public_contract"] is True
    assert report["blockers"] == [
        "hidden-evaluation-missing",
        "testpypi-evidence-missing",
    ]


def test_release_report_becomes_ready_for_maintainer_approval() -> None:
    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        hidden_evaluation=_hidden_evaluation(),
        testpypi_evidence=_testpypi_evidence(),
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "ready-for-maintainer-approval"
    assert report["blockers"] == []
    assert all(report["gates"].values())
    assert report["publication"]["main_promoted"] is False
    assert report["publication"]["pypi_published"] is False


def test_release_report_blocks_mismatched_hidden_commit_and_testpypi_artifact() -> None:
    hidden = _hidden_evaluation()
    hidden["release_commit"] = "b" * 40
    testpypi = _testpypi_evidence()
    testpypi["artifacts"][0]["sha256"] = "3" * 64

    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        hidden_evaluation=hidden,
        testpypi_evidence=testpypi,
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert "hidden-release-commit-mismatch" in report["blockers"]
    assert "testpypi-artifact-mismatch" in report["blockers"]


def test_release_report_rejects_unapproved_public_rights_payload() -> None:
    rights = _rights_manifest()
    rights["sources"][0]["rights_status"] = "pending"

    with pytest.raises(ReleaseReportError, match="unapproved public payload"):
        build_release_report(
            _artifact_audit(),
            rights,
            release_commit=_RELEASE_COMMIT,
            ci_evidence=_ci_evidence(),
            public_contract=_public_contract(),
            generated_at=_GENERATED_AT,
        )


def test_release_report_rejects_wrong_artifact_audit_runtime() -> None:
    audit = _artifact_audit()
    audit["environment"]["python_version"] = "3.12.0"

    with pytest.raises(ReleaseReportError, match="CPython 3.11.9"):
        build_release_report(
            audit,
            _rights_manifest(),
            release_commit=_RELEASE_COMMIT,
            ci_evidence=_ci_evidence(),
            public_contract=_public_contract(),
            generated_at=_GENERATED_AT,
        )


def test_release_report_blocks_non_closed_testpypi_evidence() -> None:
    evidence = _testpypi_evidence()
    evidence["unexpected"] = True

    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        hidden_evaluation=_hidden_evaluation(),
        testpypi_evidence=evidence,
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert "testpypi-evidence-incomplete" in report["blockers"]
