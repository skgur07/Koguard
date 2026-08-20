"""Contract tests for project-authored PF-005 policy slices."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluation.corpus_validator import validate_corpus_paths
from evaluation.curated_policy_intake import (
    CURATED_REPORT_SCHEMA_PATH,
    build_curated_policy_intake,
    main,
)


def test_curated_policy_intake_is_deterministic_blinded_and_validator_compatible(
    tmp_path: Path,
) -> None:
    corpus_path = tmp_path / "curated.json"
    report_path = tmp_path / "curated.report.json"

    first = build_curated_policy_intake(
        output_path=corpus_path,
        report_path=report_path,
    )
    second = build_curated_policy_intake()

    assert first == second
    assert len(first.corpus["cases"]) == 250
    assert len({case["id"] for case in first.corpus["cases"]}) == 250
    assert len({case["text"] for case in first.corpus["cases"]}) == 250
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert all(case["expected_matches"] == [] for case in first.corpus["cases"])
    assert all(case["slices"] == ["unadjudicated-intake"] for case in first.corpus["cases"])
    assert all("positive" not in case["id"] for case in first.corpus["cases"])
    assert all("negative" not in case["id"] for case in first.corpus["cases"])
    assert all(case["source"]["kind"] == "curated" for case in first.corpus["cases"])
    assert all(case["source"]["redistribution_allowed"] is True for case in first.corpus["cases"])
    assert all(case["license"] == "MIT" for case in first.corpus["cases"])
    assert validate_corpus_paths([corpus_path]).review_case_count == 250


def test_curated_report_records_design_intent_without_case_content() -> None:
    result = build_curated_policy_intake()
    report = result.report
    serialized_report = json.dumps(report, ensure_ascii=False)

    assert report["case_count"] == 250
    assert report["design_counts"] == {
        "positive_target": 100,
        "hard_negative_target": 150,
    }
    assert report["design_slice_counts"] == {
        "benign-substring": 50,
        "educational-context": 50,
        "game-term": 50,
        "quoted-context": 20,
        "token-boundary": 30,
        "username": 50,
    }
    assert report["privacy_status"] == {"synthetic": 250, "approved": 250}
    assert report["gold_ready"] is False
    assert "시발" not in serialized_report
    assert "병신" not in serialized_report


def test_curated_report_schema_is_versioned_and_closed() -> None:
    schema = json.loads(CURATED_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert schema["properties"]["design_counts"]["additionalProperties"] is False


def test_curated_cli_writes_only_aggregate_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus_path = tmp_path / "curated.json"
    report_path = tmp_path / "curated.report.json"

    exit_code = main(
        [
            "--output",
            str(corpus_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "cases=250; gold_ready=false\n"
    assert captured.err == ""
