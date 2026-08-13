"""Contract tests for matcher accuracy and cost ablation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from evaluation.ablation_runner import (
    ABLATION_MATCHERS,
    ABLATION_REPORT_SCHEMA_PATH,
    AblationError,
    profile_definitions,
    run_ablation,
)

_CORPUS_PATH = Path("evaluation/corpus/provisional-ablation.json")
_RESULT_PATH = Path("evaluation/results/provisional-ablation-windows-python311.json")
_MEASURED_AT = datetime(2026, 8, 12, tzinfo=UTC)


def test_ablation_schema_is_versioned_and_closed() -> None:
    schema = json.loads(ABLATION_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["profileResult"]["additionalProperties"] is False


def test_profiles_cover_baseline_every_matcher_prerequisites_and_current() -> None:
    profiles = profile_definitions()
    by_id = {profile.profile_id: profile for profile in profiles}

    assert set(ABLATION_MATCHERS) == {
        "repeated",
        "separator",
        "whitespace",
        "mixed",
        "keyboard",
        "jamo",
        "choseong",
        "segmented",
        "fuzzy",
    }
    assert by_id["exact-alias"].role == "baseline"
    assert by_id["segmented"].comparison_profile == "segmented-prerequisites"
    assert by_id["segmented-prerequisites"].role == "control"
    assert by_id["all-enabled"].role == "current"
    assert {profile.matcher for profile in profiles if profile.role == "candidate"} == set(
        ABLATION_MATCHERS
    )


def test_ablation_records_accuracy_increment_overlap_cost_and_limitations() -> None:
    report = run_ablation(
        [_CORPUS_PATH],
        iterations=2,
        warmups=0,
        measured_at=_MEASURED_AT,
    ).to_dict()

    assert report["schema_version"] == 1
    assert report["measured_at"] == "2026-08-12T00:00:00+00:00"
    assert report["environment"]["koguard_version"] == "0.1.0"
    assert report["corpus"]["classification"] == "provisional-regression"
    assert report["corpus"]["case_count"] == 20
    assert report["corpus"]["positive_count"] == 16
    assert report["corpus"]["hard_negative_count"] == 4
    assert len(report["corpus"]["sha256"]) == 64
    workloads = {item["workload_id"]: item for item in report["configuration"]["workloads"]}
    assert list(workloads) == ["short_chat", "maximum_input"]
    assert workloads["short_chat"]["input_length"] > 0
    assert workloads["maximum_input"]["input_length"] == 4096
    assert all(len(item["sha256"]) == 64 for item in workloads.values())

    baseline = _profile(report, "exact-alias")
    assert baseline["sentence_metrics"]["counts"] == {"tp": 3, "fp": 0, "fn": 13, "tn": 4}
    assert baseline["occurrence_metrics"]["counts"] == {"tp": 3, "fp": 0, "fn": 13}

    repeated = _matcher(report, "repeated")
    assert repeated["comparison_profile"] == "exact-alias"
    assert repeated["contribution"]["added_tp"] == 1
    assert repeated["contribution"]["added_fp"] == 0
    assert repeated["contribution"]["remaining_fn"] == 12
    assert set(repeated["cost_delta"]) == {
        "short_chat_p50_ms",
        "short_chat_p95_ms",
        "maximum_input_p50_ms",
        "maximum_input_p95_ms",
        "engine_retained_memory_bytes",
    }

    mixed = _matcher(report, "mixed")
    assert mixed["contribution"]["added_tp"] >= 1
    assert mixed["contribution"]["cross_matcher_overlap"] == 0
    assert mixed["contribution"]["unique_added"] == 1

    segmented = _matcher(report, "segmented")
    assert segmented["comparison_profile"] == "segmented-prerequisites"
    assert segmented["contribution"]["added_tp"] == 1

    current = _profile(report, "all-enabled")
    assert current["sentence_metrics"]["counts"] == {"tp": 12, "fp": 0, "fn": 4, "tn": 4}
    assert current["performance"]["short_chat"]["p50_ms"] > 0
    assert current["performance"]["short_chat"]["p95_ms"] > 0
    assert current["performance"]["maximum_input"]["p50_ms"] > 0
    assert current["performance"]["maximum_input"]["p95_ms"] > 0
    assert current["performance"]["engine_retained_memory_bytes"] > 0

    assert any("서비스 정확도" in limitation for limitation in report["limitations"])
    assert any("PF-005" in limitation for limitation in report["limitations"])


def test_report_omits_corpus_text_and_canonical_terms() -> None:
    report = run_ablation(
        [_CORPUS_PATH], iterations=1, warmups=0, measured_at=_MEASURED_AT
    ).to_dict()

    serialized = json.dumps(report, ensure_ascii=False)
    assert "시이이발" not in serialized
    assert "개새끼" not in serialized
    assert "canonical_term" not in serialized
    assert {case["case_id"] for case in report["case_results"]} == {
        f"ablation-positive-{name}"
        for name in (
            "exact",
            "alias",
            "repeated",
            "separator",
            "whitespace",
            "mixed",
            "keyboard",
            "jamo",
            "choseong",
            "segmented",
            "fuzzy",
        )
    } | {
        "ablation-negative-normal-chat",
        "ablation-negative-benign-substring",
        "ablation-negative-presentation",
        "ablation-negative-watermelon",
        "ablation-negative-finger",
        "ablation-negative-development",
        "ablation-negative-returning",
        "ablation-negative-unconfigured-separator",
        "ablation-negative-newline-keyboard",
    }


def test_review_only_corpus_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    payload["corpus_id"] = "ablation-review-only"
    payload["cases"] = [
        {
            **payload["cases"][0],
            "id": "ablation-review-only",
            "label": "review",
            "expected_matches": [],
        }
    ]
    path = tmp_path / "review-only.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(AblationError, match="no automatically evaluable cases"):
        run_ablation([path], iterations=1, warmups=0)


def test_invalid_measurement_configuration_is_rejected() -> None:
    with pytest.raises(AblationError, match="iterations must be at least 1"):
        run_ablation([_CORPUS_PATH], iterations=0, warmups=0)
    with pytest.raises(AblationError, match="warmups must be non-negative"):
        run_ablation([_CORPUS_PATH], iterations=1, warmups=-1)


def test_checked_provisional_report_matches_current_contract() -> None:
    payload = json.loads(_RESULT_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["environment"]["python_version"] == "3.11.9"
    assert payload["environment"]["koguard_version"] == "0.1.0"
    assert [item["workload_id"] for item in payload["configuration"]["workloads"]] == [
        "short_chat",
        "maximum_input",
    ]
    assert payload["configuration"]["iterations"] == 100
    assert payload["configuration"]["warmups"] == 10
    assert payload["corpus"]["sha256"] == (
        "4ad85de87665defd4fdfbe9eca89884a9f1f8fa228fd005c4afc45c862bc2ce7"
    )
    assert payload["configuration"]["profile_configuration_sha256"] == (
        "3fcd74ed874c2cafe514b1497c65e07b06421eb2807c09583184b76ad7b7fb93"
    )
    assert [item["profile_id"] for item in payload["profiles"]] == [
        profile.profile_id for profile in profile_definitions()
    ]
    assert {item["matcher"] for item in payload["matcher_ablation"]} == set(ABLATION_MATCHERS)
    assert _profile(payload, "all-enabled")["sentence_metrics"]["counts"] == {
        "tp": 12,
        "fp": 0,
        "fn": 4,
        "tn": 4,
    }


def _profile(report: dict[str, Any], profile_id: str) -> dict[str, Any]:
    return next(item for item in report["profiles"] if item["profile_id"] == profile_id)


def _matcher(report: dict[str, Any], matcher: str) -> dict[str, Any]:
    return next(item for item in report["matcher_ablation"] if item["matcher"] == matcher)
