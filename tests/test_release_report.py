"""PF-014 release decision report contract tests."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pytest
from release.release_report import (
    CI_EVIDENCE_SCHEMA_PATH,
    RELEASE_REPORT_SCHEMA_PATH,
    RIGHTS_MANIFEST_SCHEMA_PATH,
    TESTPYPI_EVIDENCE_SCHEMA_PATH,
    ReleaseReportError,
    build_release_report,
)

_RELEASE_COMMIT = "a" * 40
_SOURCE_TREE = "b" * 40
_GENERATED_AT = datetime(2026, 8, 19, tzinfo=UTC)


def _artifact_audit() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": "2026-08-19T00:00:00+00:00",
        "source": {
            "release_commit": _RELEASE_COMMIT,
            "git_tree": _SOURCE_TREE,
        },
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
                "member_count": 23,
                "bundled_notices": [
                    "koguard/data/NOTICE.md",
                    "koguard/data/KORCEN-MIT.txt",
                    "koguard/data/CURSE-DETECTION-DATA-MIT.txt",
                    "koguard-0.1.0.dist-info/licenses/LICENSE",
                ],
            },
            {
                "kind": "sdist",
                "filename": "koguard-0.1.0.tar.gz",
                "size_bytes": 250000,
                "sha256": "2" * 64,
                "member_count": 150,
                "release_evidence": ["koguard-0.1.0/LICENSE"],
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
        "schema_version": 1,
        "provider": "github-actions",
        "repository": "skgur07/Koguard",
        "workflow": "CI",
        "run_id": 1,
        "run_attempt": 1,
        "head_sha": _RELEASE_COMMIT,
        "run_url": "https://github.com/skgur07/Koguard/actions/runs/1",
        "event": "push",
        "conclusion": "success",
        "verified_at": "2026-08-19T00:00:00+00:00",
        "jobs": [
            {
                "job_id": 11,
                "name": "ubuntu-latest / CPython 3.11.9",
                "runner": "ubuntu-latest",
                "conclusion": "success",
            },
            {
                "job_id": 12,
                "name": "windows-latest / CPython 3.11.9",
                "runner": "windows-latest",
                "conclusion": "success",
            },
            {
                "job_id": 13,
                "name": "macos-latest / CPython 3.11.9",
                "runner": "macos-latest",
                "conclusion": "success",
            },
            {
                "job_id": 14,
                "name": "Verify reproducible release artifact",
                "runner": "release-artifact",
                "conclusion": "success",
            },
        ],
    }


def _public_contract() -> dict[str, bool]:
    return {
        "public_api_frozen": True,
        "readme_claims_reviewed": True,
        "limitations_documented": True,
        "core_ai_scope_separated": True,
        "private_vulnerability_reporting_enabled": True,
    }


def _metric_from_counts(counts: dict[str, int]) -> dict[str, Any]:
    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        None
        if precision is None or recall is None or precision + recall == 0
        else 2 * precision * recall / (precision + recall)
    )
    metric: dict[str, Any] = {
        "counts": counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
    if "tn" in counts:
        metric["accuracy"] = (tp + counts["tn"]) / sum(counts.values())
    return metric


def _hidden_evaluation() -> dict[str, Any]:
    public_report = json.loads(
        Path("evaluation/results/pf009-profile-evaluation.report.json").read_text(encoding="utf-8")
    )
    source = public_report["source"]
    profiles = deepcopy(public_report["profiles"])
    strict = next(profile for profile in profiles if profile["profile"] == "strict")
    balanced = next(profile for profile in profiles if profile["profile"] == "balanced")
    positive_count = source["corpus"]["positive_count"]
    hard_negative_count = source["corpus"]["hard_negative_count"]
    balanced_sentence = balanced["sentence_metrics"]["counts"]
    strict_sentence_tp = balanced_sentence["tp"] - 1
    strict["sentence_metrics"] = _metric_from_counts(
        {
            "tp": strict_sentence_tp,
            "fp": balanced_sentence["fp"],
            "fn": positive_count - strict_sentence_tp,
            "tn": hard_negative_count - balanced_sentence["fp"],
        }
    )
    balanced_occurrence = balanced["occurrence_metrics"]["counts"]
    strict_occurrence_tp = balanced_occurrence["tp"] - 1
    strict["occurrence_metrics"] = _metric_from_counts(
        {
            "tp": strict_occurrence_tp,
            "fp": balanced_occurrence["fp"],
            "fn": balanced_occurrence["tp"] + balanced_occurrence["fn"] - strict_occurrence_tp,
        }
    )
    return {
        "schema_version": 1,
        "report_kind": "hidden-evaluation",
        "release_commit": _RELEASE_COMMIT,
        "evaluation": {
            "evaluation_id": "pf014-hidden-v1",
            "evaluation_version": 1,
            "manifest_id": "koguard-release-evaluation",
            "manifest_version": 1,
            "normalization_version": "nfkc-casefold-strip-pzc-repeat-v1",
            "attestation_sha256": "3" * 64,
            "evaluated_artifact": {"kind": "wheel", "sha256": "1" * 64},
            "approval_count": 2,
            "direct_leak_count": 0,
            "normalized_leak_count": 0,
            "gold_ready": True,
        },
        "source": {
            "protected_ablation_report_sha256": "4" * 64,
            "measured_at": source["measured_at"],
            "corpus": {
                "classification": "independent-hidden-evaluation",
                "sha256": source["corpus"]["sha256"],
                "case_count": source["corpus"]["case_count"],
                "positive_count": source["corpus"]["positive_count"],
                "hard_negative_count": source["corpus"]["hard_negative_count"],
                "excluded_review_count": 0,
                "gold_ready": True,
            },
            "environment": source["environment"],
        },
        "profiles": profiles,
        "balanced_evidence": {
            "sentence_tp_delta_vs_strict": 1,
            "sentence_fp_delta_vs_strict": 0,
            "occurrence_tp_delta_vs_strict": 1,
            "occurrence_fp_delta_vs_strict": 0,
        },
        "balanced_gates": {**public_report["balanced_gates"], "passed": True},
        "balanced_slice_metrics": [
            {
                "slice": "aggregate",
                "case_count": source["corpus"]["case_count"],
                "sentence_metrics": deepcopy(balanced["sentence_metrics"]),
                "occurrence_metrics": deepcopy(balanced["occurrence_metrics"]),
            }
        ],
        "limitations": ["aggregate-only hidden release evidence"],
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
    ci_schema = json.loads(CI_EVIDENCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    rights_schema = json.loads(RIGHTS_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["additionalProperties"] is False
    assert testpypi_schema["properties"]["schema_version"]["const"] == 1
    assert testpypi_schema["properties"]["project_url"]["const"] == (
        "https://test.pypi.org/project/koguard/0.1.0/"
    )
    assert testpypi_schema["additionalProperties"] is False
    assert ci_schema["properties"]["provider"]["const"] == "github-actions"
    assert ci_schema["additionalProperties"] is False
    assert rights_schema["properties"]["project_license"]["const"] == "MIT"
    assert rights_schema["additionalProperties"] is False


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


@pytest.mark.parametrize("field", ["profiles", "balanced_slice_metrics", "limitations"])
def test_release_report_blocks_incomplete_hidden_schema(field: str) -> None:
    hidden = _hidden_evaluation()
    del hidden[field]

    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        hidden_evaluation=hidden,
        testpypi_evidence=_testpypi_evidence(),
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert "hidden-evaluation-not-ready" in report["blockers"]


def test_release_report_blocks_hidden_unknown_fields_and_inconsistent_counts() -> None:
    hidden = _hidden_evaluation()
    hidden["unexpected"] = True
    hidden["source"]["corpus"]["case_count"] += 1

    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        hidden_evaluation=hidden,
        testpypi_evidence=_testpypi_evidence(),
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert "hidden-evaluation-not-ready" in report["blockers"]


def test_release_report_blocks_hidden_artifact_not_used_by_audit() -> None:
    hidden = _hidden_evaluation()
    hidden["evaluation"]["evaluated_artifact"]["sha256"] = "9" * 64

    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=_ci_evidence(),
        public_contract=_public_contract(),
        hidden_evaluation=hidden,
        testpypi_evidence=_testpypi_evidence(),
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert "hidden-artifact-mismatch" in report["blockers"]


def test_release_report_rejects_artifact_audit_from_another_commit() -> None:
    audit = _artifact_audit()
    audit["source"]["release_commit"] = "c" * 40

    with pytest.raises(ReleaseReportError, match="release commit"):
        build_release_report(
            audit,
            _rights_manifest(),
            release_commit=_RELEASE_COMMIT,
            ci_evidence=_ci_evidence(),
            public_contract=_public_contract(),
            generated_at=_GENERATED_AT,
        )


def test_release_report_blocks_non_closed_or_failed_ci_evidence() -> None:
    ci = _ci_evidence()
    ci["unexpected"] = True
    ci["jobs"][0]["conclusion"] = "failure"

    report = build_release_report(
        _artifact_audit(),
        _rights_manifest(),
        release_commit=_RELEASE_COMMIT,
        ci_evidence=ci,
        public_contract=_public_contract(),
        generated_at=_GENERATED_AT,
    )

    assert report["decision"] == "blocked"
    assert "ci-evidence-not-ready" in report["blockers"]


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
