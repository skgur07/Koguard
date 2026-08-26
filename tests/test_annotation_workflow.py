"""Contract tests for the blinded PF-005 annotation workflow."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.annotation_workflow import (
    ANNOTATION_BATCH_SCHEMA_PATH,
    ANNOTATION_REPORT_SCHEMA_PATH,
    AnnotationWorkflowError,
    adjudicate_annotation_batches,
    export_annotation_batch,
    main,
    merge_annotation_batches,
)
from evaluation.corpus_validator import validate_corpus_paths

_PUBLISHED_ADJUDICATION_REPORT_PATH = (
    Path(__file__).parents[1] / "evaluation" / "results" / "pf005-batch-001-adjudicated.report.json"
)
_PUBLISHED_BALANCED_ADJUDICATION_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf005-balanced-batch-001-adjudicated.report.json"
)
_PUBLISHED_BALANCED_BATCH_002_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf005-balanced-batch-002-adjudicated.report.json"
)
_PUBLISHED_HARD_NEGATIVE_BATCH_001_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf005-hard-negative-batch-001-adjudicated.report.json"
)
_PUBLISHED_POLICY_REAUDIT_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf005-policy-reaudit-v1-adjudicated.report.json"
)


def test_annotation_schemas_are_versioned_and_closed() -> None:
    batch_schema = json.loads(ANNOTATION_BATCH_SCHEMA_PATH.read_text(encoding="utf-8"))
    report_schema = json.loads(ANNOTATION_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert batch_schema["properties"]["schema_version"]["const"] == 1
    assert batch_schema["additionalProperties"] is False
    assert batch_schema["$defs"]["annotation"]["additionalProperties"] is False
    assert batch_schema["$defs"]["annotation"]["properties"]["slices"]["items"]["$ref"] == (
        "corpus.schema.json#/$defs/case/properties/slices/items"
    )
    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["additionalProperties"] is False


def test_published_adjudication_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_ADJUDICATION_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["batch_case_count"] == 100
    assert sum(report["batch_counts"].values()) == 100
    assert report["quality_counts"]["double_reviewed"] == 100
    assert report["adjudication_counts"] == {
        "eligible": 70,
        "resolved": 68,
        "unresolved": 2,
        "privacy_excluded": 0,
    }
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_published_balanced_adjudication_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_BALANCED_ADJUDICATION_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["batch_case_count"] == 500
    assert report["batch_counts"] == {
        "positive": 202,
        "hard-negative": 242,
        "review": 56,
    }
    assert report["corpus_counts"] == {
        "positive": 264,
        "hard-negative": 272,
        "review": 1964,
    }
    assert report["quality_counts"] == {
        "double_reviewed": 500,
        "consensus": 113,
        "disagreement": 387,
        "privacy_excluded": 0,
        "pending_privacy": 0,
    }
    assert report["adjudication_counts"] == {
        "eligible": 387,
        "resolved": 334,
        "unresolved": 53,
        "privacy_excluded": 0,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_published_balanced_batch_002_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_BALANCED_BATCH_002_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["batch_case_count"] == 500
    assert report["batch_counts"] == {
        "positive": 112,
        "hard-negative": 324,
        "review": 64,
    }
    assert report["corpus_counts"] == {
        "positive": 377,
        "hard-negative": 595,
        "review": 1528,
    }
    assert report["quality_counts"] == {
        "double_reviewed": 500,
        "consensus": 207,
        "disagreement": 293,
        "privacy_excluded": 0,
        "pending_privacy": 0,
    }
    assert report["adjudication_counts"] == {
        "eligible": 293,
        "resolved": 281,
        "unresolved": 12,
        "privacy_excluded": 0,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_published_hard_negative_batch_001_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_HARD_NEGATIVE_BATCH_001_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["batch_case_count"] == 500
    assert report["batch_counts"] == {
        "positive": 12,
        "hard-negative": 471,
        "review": 17,
    }
    assert report["quality_counts"] == {
        "double_reviewed": 500,
        "consensus": 48,
        "disagreement": 452,
        "privacy_excluded": 0,
        "pending_privacy": 0,
    }
    assert report["adjudication_counts"] == {
        "eligible": 452,
        "resolved": 442,
        "unresolved": 10,
        "privacy_excluded": 0,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_published_policy_reaudit_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_POLICY_REAUDIT_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["batch_case_count"] == 3
    assert report["batch_counts"] == {
        "positive": 3,
        "hard-negative": 0,
        "review": 0,
    }
    assert report["quality_counts"] == {
        "double_reviewed": 3,
        "consensus": 0,
        "disagreement": 3,
        "privacy_excluded": 0,
        "pending_privacy": 0,
    }
    assert report["adjudication_counts"] == {
        "eligible": 3,
        "resolved": 3,
        "unresolved": 0,
        "privacy_excluded": 0,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_export_is_deterministic_blinded_and_review_only(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())

    first = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-a-primary",
        reviewer_id="reviewer-a",
        offset=0,
        limit=2,
    )
    second = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-a-primary",
        reviewer_id="reviewer-a",
        offset=0,
        limit=2,
    )

    assert first == second
    assert first["corpus_sha256"] == hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    assert [case["case_id"] for case in first["cases"]] == ["review-a", "review-b"]
    assert all(case["label"] == "review" for case in first["cases"])
    assert all(case["privacy_status"] == "pending" for case in first["cases"])
    assert all(case["expected_matches"] == [] for case in first["cases"])
    assert all(case["slices"] == ["unadjudicated-intake"] for case in first["cases"])
    serialized = json.dumps(first, ensure_ascii=False)
    assert "source_label" not in serialized
    assert "detector_prediction" not in serialized
    assert "existing-positive" not in serialized


def test_export_cli_prints_only_non_sensitive_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_text = "CLI에 노출되면 안 되는 원문"
    corpus = _corpus()
    corpus["cases"][0]["text"] = secret_text
    corpus_path = _write_json(tmp_path / "corpus.json", corpus)
    output_path = tmp_path / "annotation-work" / "primary.json"

    exit_code = main(
        [
            "export",
            str(corpus_path),
            "--annotation-set-id",
            "batch-a-primary",
            "--reviewer-id",
            "reviewer-a",
            "--limit",
            "2",
            "--output",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "exported=2" in captured.out
    assert secret_text not in captured.out
    assert captured.err == ""
    assert output_path.is_file()


def test_export_refuses_to_overwrite_the_source_corpus(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    original_bytes = corpus_path.read_bytes()

    with pytest.raises(AnnotationWorkflowError, match="output must not overwrite an input"):
        export_annotation_batch(
            corpus_path,
            annotation_set_id="batch-primary",
            reviewer_id="reviewer-a",
            output_path=corpus_path,
        )

    assert corpus_path.read_bytes() == original_bytes


def test_merge_promotes_only_double_review_consensus(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-a-primary",
        reviewer_id="reviewer-a",
        limit=2,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-a-secondary",
        reviewer_id="reviewer-b",
        limit=2,
    )
    for batch in (primary, secondary):
        batch["cases"][0].update(
            {
                "privacy_status": "approved",
                "label": "positive",
                "expected_matches": [{"start": 0, "end": 3, "canonical_term": "금칙어"}],
                "slices": ["direct"],
                "notes": "직접 표현으로 판정",
            }
        )
        batch["cases"][1].update(
            {
                "privacy_status": "approved",
                "label": "hard-negative",
                "expected_matches": [],
                "slices": ["benign-substring"],
                "notes": "정상 복합어로 판정",
            }
        )
    primary_path = _write_json(tmp_path / "primary.json", primary)
    secondary_path = _write_json(tmp_path / "secondary.json", secondary)
    output_path = tmp_path / "merged.json"
    report_path = tmp_path / "report.json"

    result = merge_annotation_batches(
        corpus_path,
        primary_path,
        secondary_path,
        output_path=output_path,
        report_path=report_path,
    )

    merged_cases = {case["id"]: case for case in result.corpus["cases"]}
    assert merged_cases["review-a"]["label"] == "positive"
    assert merged_cases["review-a"]["expected_matches"] == [
        {"start": 0, "end": 3, "canonical_term": "금칙어"}
    ]
    assert merged_cases["review-a"]["slices"] == ["direct"]
    assert merged_cases["review-b"]["label"] == "hard-negative"
    assert merged_cases["review-b"]["slices"] == ["benign-substring"]
    assert merged_cases["existing-positive"]["label"] == "positive"
    assert result.report["batch_counts"] == {
        "positive": 1,
        "hard-negative": 1,
        "review": 0,
    }
    assert result.report["quality_counts"] == {
        "double_reviewed": 2,
        "consensus": 2,
        "disagreement": 0,
        "privacy_excluded": 0,
        "pending_privacy": 0,
    }
    assert result.report["slice_counts"] == {"benign-substring": 1, "direct": 1}
    assert result.report["gold_ready"] is False
    assert validate_corpus_paths([output_path]).review_case_count == 1
    assert report_path.is_file()


def test_merge_keeps_disagreement_exclusion_and_pending_cases_in_review(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-all-primary",
        reviewer_id="reviewer-a",
        limit=3,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-all-secondary",
        reviewer_id="reviewer-b",
        limit=3,
    )
    _approve_negative(primary["cases"][0])
    _approve_positive(secondary["cases"][0])
    _approve_negative(primary["cases"][1])
    secondary["cases"][1]["privacy_status"] = "exclude"
    _approve_negative(primary["cases"][2])

    result = merge_annotation_batches(
        corpus_path,
        _write_json(tmp_path / "primary.json", primary),
        _write_json(tmp_path / "secondary.json", secondary),
    )

    merged_cases = {case["id"]: case for case in result.corpus["cases"]}
    for case_id in ("review-a", "review-b", "review-c"):
        assert merged_cases[case_id]["label"] == "review"
        assert merged_cases[case_id]["expected_matches"] == []
        assert merged_cases[case_id]["slices"] == ["unadjudicated-intake"]
    assert result.report["quality_counts"] == {
        "double_reviewed": 1,
        "consensus": 0,
        "disagreement": 1,
        "privacy_excluded": 1,
        "pending_privacy": 1,
    }
    serialized_report = json.dumps(result.report, ensure_ascii=False)
    assert "금칙어 문장" not in serialized_report
    assert "canonical_term" not in serialized_report


def test_adjudication_resolves_only_initial_disagreements(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=3,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=3,
    )
    adjudicator = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-adjudicator",
        reviewer_id="reviewer-c",
        limit=3,
    )
    for batch in (primary, secondary):
        _approve_positive(batch["cases"][0])
        _approve_negative(batch["cases"][2])
    _approve_negative(primary["cases"][1])
    _approve_positive(secondary["cases"][1])
    _approve_positive(adjudicator["cases"][1])

    result = adjudicate_annotation_batches(
        corpus_path,
        _write_json(tmp_path / "primary.json", primary),
        _write_json(tmp_path / "secondary.json", secondary),
        _write_json(tmp_path / "adjudicator.json", adjudicator),
    )

    merged_cases = {case["id"]: case for case in result.corpus["cases"]}
    assert merged_cases["review-a"]["label"] == "positive"
    assert merged_cases["review-b"]["label"] == "positive"
    assert merged_cases["review-c"]["label"] == "hard-negative"
    assert result.report["quality_counts"] == {
        "double_reviewed": 3,
        "consensus": 2,
        "disagreement": 1,
        "privacy_excluded": 0,
        "pending_privacy": 0,
    }
    assert result.report["adjudication_counts"] == {
        "eligible": 1,
        "resolved": 1,
        "unresolved": 0,
        "privacy_excluded": 0,
    }


def test_adjudication_requires_a_third_reviewer_and_completed_disagreement(
    tmp_path: Path,
) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=1,
    )
    _approve_negative(primary["cases"][0])
    _approve_positive(secondary["cases"][0])
    adjudicator = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-adjudicator",
        reviewer_id="reviewer-a",
        limit=1,
    )

    with pytest.raises(AnnotationWorkflowError, match="reviewer IDs must be distinct"):
        adjudicate_annotation_batches(
            corpus_path,
            _write_json(tmp_path / "primary.json", primary),
            _write_json(tmp_path / "secondary.json", secondary),
            _write_json(tmp_path / "adjudicator.json", adjudicator),
        )

    adjudicator["reviewer_id"] = "reviewer-c"
    with pytest.raises(AnnotationWorkflowError, match="adjudication is incomplete"):
        adjudicate_annotation_batches(
            corpus_path,
            tmp_path / "primary.json",
            tmp_path / "secondary.json",
            _write_json(tmp_path / "adjudicator.json", adjudicator),
        )


def test_adjudication_can_explicitly_retain_review(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=1,
    )
    adjudicator = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-adjudicator",
        reviewer_id="reviewer-c",
        limit=1,
    )
    _approve_negative(primary["cases"][0])
    _approve_positive(secondary["cases"][0])
    adjudicator["cases"][0]["privacy_status"] = "approved"

    result = adjudicate_annotation_batches(
        corpus_path,
        _write_json(tmp_path / "primary.json", primary),
        _write_json(tmp_path / "secondary.json", secondary),
        _write_json(tmp_path / "adjudicator.json", adjudicator),
    )

    assert result.report["adjudication_counts"]["resolved"] == 0
    assert result.report["adjudication_counts"]["unresolved"] == 1
    assert result.corpus["cases"][1]["label"] == "review"


def test_adjudication_cli_prints_aggregate_counts_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = _corpus()
    secret_text = "민감한 판정 원문"
    corpus["cases"][1]["text"] = secret_text
    corpus_path = _write_json(tmp_path / "corpus.json", corpus)
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=1,
    )
    adjudicator = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-adjudicator",
        reviewer_id="reviewer-c",
        limit=1,
    )
    _approve_negative(primary["cases"][0])
    _approve_positive(secondary["cases"][0])
    _approve_positive(adjudicator["cases"][0])

    exit_code = main(
        [
            "adjudicate",
            str(corpus_path),
            str(_write_json(tmp_path / "primary.json", primary)),
            str(_write_json(tmp_path / "secondary.json", secondary)),
            str(_write_json(tmp_path / "adjudicator.json", adjudicator)),
            "--output",
            str(tmp_path / "adjudicated.json"),
            "--report",
            str(tmp_path / "report.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "batch=1" in captured.out
    assert "adjudicated=1" in captured.out
    assert "unresolved=0" in captured.out
    assert secret_text not in captured.out
    assert "canonical_term" not in captured.out
    assert captured.err == ""


def test_merge_rejects_same_reviewer_and_tampered_text_without_echoing_text(tmp_path: Path) -> None:
    secret_text = "오류에 노출되면 안 되는 민감 원문"
    corpus = _corpus()
    corpus["cases"][0]["text"] = secret_text
    corpus_path = _write_json(tmp_path / "corpus.json", corpus)
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = copy.deepcopy(primary)
    secondary["annotation_set_id"] = "batch-secondary"

    with pytest.raises(AnnotationWorkflowError, match="reviewer IDs must differ"):
        merge_annotation_batches(
            corpus_path,
            _write_json(tmp_path / "primary.json", primary),
            _write_json(tmp_path / "secondary.json", secondary),
        )

    secondary["reviewer_id"] = "reviewer-b"
    secondary["cases"][0]["text"] = "변조된 원문"
    with pytest.raises(AnnotationWorkflowError, match="source text mismatch") as captured:
        merge_annotation_batches(
            corpus_path,
            _write_json(tmp_path / "primary.json", primary),
            _write_json(tmp_path / "secondary.json", secondary),
        )

    assert secret_text not in str(captured.value)


def test_merge_rejects_invalid_approved_annotation(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=1,
    )
    for batch in (primary, secondary):
        batch["cases"][0].update(
            {
                "privacy_status": "approved",
                "label": "positive",
                "expected_matches": [],
                "slices": ["unadjudicated-intake"],
                "notes": "잘못된 확정 판정",
            }
        )

    with pytest.raises(AnnotationWorkflowError, match="positive annotation requires a match"):
        merge_annotation_batches(
            corpus_path,
            _write_json(tmp_path / "primary.json", primary),
            _write_json(tmp_path / "secondary.json", secondary),
        )


def test_merge_rejects_invalid_unicode_annotation_metadata(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=1,
    )
    for batch in (primary, secondary):
        batch["cases"][0].update(
            {
                "privacy_status": "approved",
                "label": "positive",
                "expected_matches": [{"start": 0, "end": 3, "canonical_term": "\ud800"}],
                "slices": ["direct"],
                "notes": "직접 표현",
            }
        )
    primary_path = tmp_path / "primary.json"
    secondary_path = tmp_path / "secondary.json"
    primary_path.write_text(json.dumps(primary), encoding="utf-8")
    secondary_path.write_text(json.dumps(secondary), encoding="utf-8")

    with pytest.raises(AnnotationWorkflowError, match="canonical_term is invalid"):
        merge_annotation_batches(corpus_path, primary_path, secondary_path)


def test_merge_refuses_overlapping_input_and_output_paths(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    primary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-primary",
        reviewer_id="reviewer-a",
        limit=1,
    )
    secondary = export_annotation_batch(
        corpus_path,
        annotation_set_id="batch-secondary",
        reviewer_id="reviewer-b",
        limit=1,
    )
    primary_path = _write_json(tmp_path / "primary.json", primary)
    secondary_path = _write_json(tmp_path / "secondary.json", secondary)

    with pytest.raises(AnnotationWorkflowError, match="output must not overwrite an input"):
        merge_annotation_batches(
            corpus_path,
            primary_path,
            secondary_path,
            output_path=primary_path,
        )
    with pytest.raises(AnnotationWorkflowError, match="output and report paths must differ"):
        merge_annotation_batches(
            corpus_path,
            primary_path,
            secondary_path,
            output_path=tmp_path / "result.json",
            report_path=tmp_path / "result.json",
        )


def _approve_negative(annotation: dict[str, Any]) -> None:
    annotation.update(
        {
            "privacy_status": "approved",
            "label": "hard-negative",
            "expected_matches": [],
            "slices": ["benign-substring"],
            "notes": "정상 문맥",
        }
    )


def _approve_positive(annotation: dict[str, Any]) -> None:
    annotation.update(
        {
            "privacy_status": "approved",
            "label": "positive",
            "expected_matches": [{"start": 0, "end": 3, "canonical_term": "금칙어"}],
            "slices": ["direct"],
            "notes": "직접 표현",
        }
    )


def _corpus() -> dict[str, Any]:
    source = {
        "kind": "licensed",
        "name": "Unit licensed source",
        "reference": "https://example.invalid/source",
        "revision": "fixed-revision",
        "redistribution_allowed": True,
    }
    return {
        "schema_version": 1,
        "corpus_id": "unit-review-corpus",
        "cases": [
            _review_case("review-c", "세 번째 검토 문장", source),
            _review_case("review-a", "금칙어 문장", source),
            {
                "id": "existing-positive",
                "text": "기존 금칙어",
                "label": "positive",
                "expected_matches": [{"start": 3, "end": 6, "canonical_term": "금칙어"}],
                "slices": ["direct"],
                "source": source,
                "license": "MIT",
                "split": "tuning",
                "notes": "기존 확정 사례",
            },
            _review_case("review-b", "정상 복합어 문장", source),
        ],
    }


def _review_case(case_id: str, text: str, source: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": case_id,
        "text": text,
        "label": "review",
        "expected_matches": [],
        "slices": ["unadjudicated-intake"],
        "source": source,
        "license": "MIT",
        "split": "tuning",
        "notes": "Unadjudicated intake.",
    }


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
