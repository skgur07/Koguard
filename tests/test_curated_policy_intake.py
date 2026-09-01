"""Contract tests for project-authored PF-005 policy slices."""

from __future__ import annotations

import json
from pathlib import Path
from unicodedata import normalize

import pytest
from evaluation.corpus_validator import validate_corpus_paths
from evaluation.curated_policy_intake import (
    CURATED_REPORT_SCHEMA_PATH,
    build_curated_policy_buffer_intake,
    build_curated_policy_intake,
    build_curated_positive_slice_intake,
    main,
)

_PUBLISHED_BUFFER_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "curated-hard-negative-buffer-v1.report.json"
)
_PUBLISHED_POSITIVE_SLICE_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "curated-positive-slice-buffer-v1.report.json"
)
_PUBLISHED_POSITIVE_SLICE_CORPUS_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "corpus"
    / "tuning"
    / "curated-positive-slice-buffer-v1.json"
)


def test_curated_positive_slice_buffer_adds_480_disjoint_blinded_targets(
    tmp_path: Path,
) -> None:
    base = build_curated_policy_intake()
    hard_negative_buffer = build_curated_policy_buffer_intake()
    corpus_path = tmp_path / "positive-slices.json"
    report_path = tmp_path / "positive-slices.report.json"

    first = build_curated_positive_slice_intake(
        output_path=corpus_path,
        report_path=report_path,
    )
    second = build_curated_positive_slice_intake()

    assert first == second
    assert first.report["case_count"] == 480
    assert first.report["design_counts"] == {
        "positive_target": 240,
        "hard_negative_target": 240,
    }
    assert first.report["design_slice_counts"] == {
        "alias": 60,
        "jamo": 60,
        "keyboard": 60,
        "mixed-gap": 60,
        "repeated": 60,
        "separator": 60,
        "unicode": 60,
        "whitespace": 60,
    }
    prior_texts = {
        case["text"]
        for corpus in (base.corpus, hard_negative_buffer.corpus)
        for case in corpus["cases"]
    }
    assert {case["text"] for case in first.corpus["cases"]}.isdisjoint(prior_texts)
    prior_normalized = {normalize("NFKC", text).casefold() for text in prior_texts}
    current_normalized = {
        normalize("NFKC", case["text"]).casefold() for case in first.corpus["cases"]
    }
    assert current_normalized.isdisjoint(prior_normalized)
    assert len(current_normalized) == 480
    assert len({case["id"] for case in first.corpus["cases"]}) == 480
    assert len({case["text"] for case in first.corpus["cases"]}) == 480
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert all(case["expected_matches"] == [] for case in first.corpus["cases"])
    assert all(case["slices"] == ["unadjudicated-intake"] for case in first.corpus["cases"])
    assert all("positive" not in case["id"] for case in first.corpus["cases"])
    assert all(
        case["source"]["revision"] == "curated-positive-slice-buffer-v1"
        for case in first.corpus["cases"]
    )
    assert json.loads(_PUBLISHED_POSITIVE_SLICE_CORPUS_PATH.read_text(encoding="utf-8")) == (
        first.corpus
    )
    assert validate_corpus_paths([corpus_path]).review_case_count == 480


def test_published_curated_positive_slice_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_POSITIVE_SLICE_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["case_count"] == 480
    assert report["design_counts"] == {
        "positive_target": 240,
        "hard_negative_target": 240,
    }
    assert report["design_slice_counts"] == {
        "alias": 60,
        "jamo": 60,
        "keyboard": 60,
        "mixed-gap": 60,
        "repeated": 60,
        "separator": 60,
        "unicode": 60,
        "whitespace": 60,
    }
    assert report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": 480,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_curated_policy_buffer_adds_100_disjoint_hard_negative_targets(
    tmp_path: Path,
) -> None:
    base = build_curated_policy_intake()
    corpus_path = tmp_path / "buffer.json"
    report_path = tmp_path / "buffer.report.json"

    first = build_curated_policy_buffer_intake(
        output_path=corpus_path,
        report_path=report_path,
    )
    second = build_curated_policy_buffer_intake()

    assert first == second
    assert first.report["case_count"] == 100
    assert first.report["design_counts"] == {
        "positive_target": 0,
        "hard_negative_target": 100,
    }
    assert {case["text"] for case in first.corpus["cases"]}.isdisjoint(
        case["text"] for case in base.corpus["cases"]
    )
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert all(
        case["source"]["revision"] == "curated-policy-buffer-v1" for case in first.corpus["cases"]
    )
    assert validate_corpus_paths([corpus_path]).review_case_count == 100


def test_published_curated_buffer_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_BUFFER_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["case_count"] == 100
    assert report["design_counts"] == {
        "positive_target": 0,
        "hard_negative_target": 100,
    }
    assert report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": 100,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


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
    assert schema["properties"]["corpus_id"]["enum"] == [
        "koguard-curated-policy-slices-v1",
        "koguard-curated-hard-negative-buffer-v1",
        "koguard-curated-positive-slice-buffer-v1",
    ]
    assert len(schema["allOf"]) == 3


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


def test_curated_buffer_cli_writes_only_aggregate_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus_path = tmp_path / "buffer.json"
    report_path = tmp_path / "buffer.report.json"

    exit_code = main(
        [
            "--kind",
            "hard-negative-buffer",
            "--output",
            str(corpus_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "cases=100; gold_ready=false\n"
    assert captured.err == ""
    assert validate_corpus_paths([corpus_path]).review_case_count == 100


def test_curated_positive_slice_cli_writes_only_aggregate_output(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus_path = tmp_path / "positive-slices.json"
    report_path = tmp_path / "positive-slices.report.json"

    exit_code = main(
        [
            "--kind",
            "positive-slice-buffer",
            "--output",
            str(corpus_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "cases=480; gold_ready=false\n"
    assert captured.err == ""
    assert validate_corpus_paths([corpus_path]).review_case_count == 480
