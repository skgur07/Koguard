"""PF-014 privacy-safe hidden evaluation report contract tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.hidden_evaluation_report import (
    HIDDEN_ATTESTATION_SCHEMA_PATH,
    HIDDEN_EVALUATION_REPORT_SCHEMA_PATH,
    HiddenEvaluationReportError,
    build_hidden_evaluation_report,
)

_SOURCE_PATH = Path("evaluation/results/provisional-ablation-windows-python311.json")
_COMMITTED_REPORT_PATH = Path("evaluation/results/pf014-hidden-khaters-v1.aggregate.json")
_RELEASE_COMMIT = "a" * 40
_EVALUATED_WHEEL_SHA256 = "c" * 64


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _attestation(source: dict[str, Any], source_sha256: str) -> dict[str, Any]:
    corpus = source["corpus"]
    return {
        "schema_version": 1,
        "evaluation_id": "pf014-hidden-v1",
        "evaluation_version": 1,
        "release_commit": _RELEASE_COMMIT,
        "protected_ablation_report_sha256": source_sha256,
        "evaluated_artifact": {
            "kind": "wheel",
            "sha256": _EVALUATED_WHEEL_SHA256,
        },
        "manifest": {
            "manifest_id": "koguard-release-evaluation",
            "manifest_version": 1,
            "normalization_version": "nfkc-casefold-strip-pzc-repeat-v1",
            "direct_leak_count": 0,
            "normalized_leak_count": 0,
        },
        "corpus": {
            "sha256": corpus["sha256"],
            "case_count": corpus["case_count"],
            "positive_count": corpus["positive_count"],
            "hard_negative_count": corpus["hard_negative_count"],
            "excluded_review_count": corpus["excluded_review_count"],
        },
        "review": {
            "annotation_status": "independent-consensus",
            "privacy_review_complete": True,
            "rights_review_complete": True,
            "custodian_approval_id": "custodian-pf014-v1",
            "release_reviewer_approval_id": "release-review-pf014-v1",
        },
    }


def test_hidden_evaluation_contracts_are_versioned_and_closed() -> None:
    attestation_schema = json.loads(HIDDEN_ATTESTATION_SCHEMA_PATH.read_text(encoding="utf-8"))
    report_schema = json.loads(HIDDEN_EVALUATION_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert attestation_schema["properties"]["schema_version"]["const"] == 1
    assert attestation_schema["additionalProperties"] is False
    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["properties"]["report_kind"]["const"] == "hidden-evaluation"
    assert report_schema["additionalProperties"] is False


def test_hidden_report_exposes_only_aggregate_release_evidence() -> None:
    source = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    source_sha256 = _sha256(_SOURCE_PATH)
    attestation = _attestation(source, source_sha256)

    report = build_hidden_evaluation_report(
        source,
        source_sha256=source_sha256,
        attestation=attestation,
        attestation_sha256="b" * 64,
    )

    assert report["schema_version"] == 1
    assert report["report_kind"] == "hidden-evaluation"
    assert report["release_commit"] == _RELEASE_COMMIT
    assert report["evaluation"]["gold_ready"] is True
    assert report["evaluation"]["evaluated_artifact"] == {
        "kind": "wheel",
        "sha256": _EVALUATED_WHEEL_SHA256,
    }
    assert report["source"]["corpus"]["classification"] == "independent-hidden-evaluation"
    assert [profile["profile"] for profile in report["profiles"]] == [
        "strict",
        "balanced",
        "aggressive",
    ]
    assert report["balanced_slice_metrics"]

    serialized = json.dumps(report, ensure_ascii=False)
    assert "case_results" not in serialized
    assert "canonical_term" not in serialized
    for case in source["case_results"]:
        assert case["case_id"] not in serialized


def test_hidden_report_rejects_attestation_not_bound_to_source() -> None:
    source = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    source_sha256 = _sha256(_SOURCE_PATH)
    attestation = _attestation(source, source_sha256)
    attestation["corpus"]["sha256"] = "0" * 64

    with pytest.raises(HiddenEvaluationReportError, match="corpus evidence"):
        build_hidden_evaluation_report(
            source,
            source_sha256=source_sha256,
            attestation=attestation,
            attestation_sha256="b" * 64,
        )


def test_hidden_report_rejects_invalid_evaluated_artifact() -> None:
    source = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    source_sha256 = _sha256(_SOURCE_PATH)
    attestation = _attestation(source, source_sha256)
    attestation["evaluated_artifact"]["sha256"] = "not-a-digest"

    with pytest.raises(HiddenEvaluationReportError, match="evaluated_artifact"):
        build_hidden_evaluation_report(
            source,
            source_sha256=source_sha256,
            attestation=attestation,
            attestation_sha256="b" * 64,
        )


def test_hidden_report_rejects_leaks_and_non_independent_approval() -> None:
    source = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    source_sha256 = _sha256(_SOURCE_PATH)
    attestation = _attestation(source, source_sha256)
    attestation["manifest"]["normalized_leak_count"] = 1

    with pytest.raises(HiddenEvaluationReportError, match="leak counts"):
        build_hidden_evaluation_report(
            source,
            source_sha256=source_sha256,
            attestation=attestation,
            attestation_sha256="b" * 64,
        )


def test_hidden_report_rejects_unknown_attestation_fields() -> None:
    source = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    source_sha256 = _sha256(_SOURCE_PATH)
    attestation = _attestation(source, source_sha256)
    attestation["raw_case_ids"] = ["must-not-be-accepted"]

    with pytest.raises(HiddenEvaluationReportError, match="closed contract"):
        build_hidden_evaluation_report(
            source,
            source_sha256=source_sha256,
            attestation=attestation,
            attestation_sha256="b" * 64,
        )


def test_hidden_report_requires_distinct_approvals() -> None:
    source = json.loads(_SOURCE_PATH.read_text(encoding="utf-8"))
    source_sha256 = _sha256(_SOURCE_PATH)
    attestation = _attestation(source, source_sha256)
    attestation["review"]["release_reviewer_approval_id"] = attestation["review"][
        "custodian_approval_id"
    ]
    with pytest.raises(HiddenEvaluationReportError, match="distinct"):
        build_hidden_evaluation_report(
            source,
            source_sha256=source_sha256,
            attestation=attestation,
            attestation_sha256="b" * 64,
        )


def test_committed_hidden_report_is_aggregate_only_and_passes_release_gates() -> None:
    report = json.loads(_COMMITTED_REPORT_PATH.read_text(encoding="utf-8"))

    canonical_report = json.dumps(
        report, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode()
    assert hashlib.sha256(canonical_report).hexdigest() == (
        "92940b0fcc828ef1e80879698d700e826ef9691efbe37dda0e38f65d9379ced9"
    )
    assert report["release_commit"] == "813fc36c6988a7bdab68027964a206e970ab9f52"
    assert report["source"]["corpus"] == {
        "sha256": "46ea020a06cb0242cf2f0556b34ae5ffb66c8f1119bd0f4eafd50443d6461ff3",
        "case_count": 424,
        "positive_count": 16,
        "hard_negative_count": 408,
        "excluded_review_count": 0,
        "classification": "independent-hidden-evaluation",
        "gold_ready": True,
    }
    assert report["balanced_evidence"] == {
        "sentence_tp_delta_vs_strict": 2,
        "sentence_fp_delta_vs_strict": 0,
        "occurrence_tp_delta_vs_strict": 2,
        "occurrence_fp_delta_vs_strict": 0,
    }
    assert report["balanced_gates"]["passed"] is True

    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden_key in ("case_results", "case_id", "canonical_term", "reviewer_id"):
        assert f'"{forbidden_key}"' not in serialized
