"""Contract tests for deterministic source-balanced review queues."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.review_queue_planner import ReviewQueueError, main, prepare_review_queue

_PUBLISHED_SLICE_PRIORITY_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf005-slice-priority-batch-001.report.json"
)


def test_prepare_review_queue_is_deterministic_source_balanced_and_blinded(
    tmp_path: Path,
) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())

    first = prepare_review_queue(
        corpus_path,
        queue_id="unit-queue-v1",
        corpus_id="unit-review-queue-v1",
        limit=5,
    )
    second = prepare_review_queue(
        corpus_path,
        queue_id="unit-queue-v1",
        corpus_id="unit-review-queue-v1",
        limit=5,
    )

    assert first == second
    assert len(first.corpus["cases"]) == 5
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert sorted(row["selected_count"] for row in first.report["source_statistics"]) == [2, 3]
    assert first.report["selection"] == "source-round-robin-sha256-v1"
    serialized = json.dumps(first.report, ensure_ascii=False)
    for forbidden in ("case-a", "원문 A", "text", "case_id"):
        assert forbidden not in serialized


def test_prepare_review_queue_prioritizes_detector_blind_surface_signals(
    tmp_path: Path,
) -> None:
    corpus = _corpus()
    signal_texts = {
        "case-a": "표면 ㅅㅂ 신호",
        "case-b": "한.글 separator",
        "case-c": "반복ㅋㅋㅋㅋ",
        "case-d": "ASCII token sample",
        "case-e": "한 글",
        "case-f": "일반 문장",
    }
    for case in corpus["cases"]:
        if case["id"] in signal_texts:
            case["text"] = signal_texts[case["id"]]
    corpus_path = _write_json(tmp_path / "corpus.json", corpus)

    first = prepare_review_queue(
        corpus_path,
        queue_id="unit-surface-priority-v1",
        corpus_id="unit-surface-priority-v1",
        limit=4,
        surface_priority=True,
    )
    second = prepare_review_queue(
        corpus_path,
        queue_id="unit-surface-priority-v1",
        corpus_id="unit-surface-priority-v1",
        limit=4,
        surface_priority=True,
    )

    assert first == second
    assert first.report["selection"] == "surface-signal-source-round-robin-sha256-v1"
    assert first.report["selected_with_surface_signal_count"] == 4
    assert first.report["surface_signal_candidate_counts"] == {
        "ascii-token": 2,
        "choseong-run": 2,
        "compat-jamo": 2,
        "hangul-separator": 1,
        "repeated-character": 1,
        "single-hangul-gap": 1,
    }
    assert sum(first.report["surface_signal_selected_counts"].values()) >= 4
    assert first.report["uses_detector_predictions"] is False
    assert first.report["uses_upstream_labels"] is False
    serialized = json.dumps(first.report, ensure_ascii=False)
    for forbidden in ("case-a", "ㅅㅂ", "text", "case_id"):
        assert forbidden not in serialized


def test_published_slice_priority_queue_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_SLICE_PRIORITY_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["selection"] == "surface-signal-source-round-robin-sha256-v1"
    assert report["eligible_review_count"] == 419
    assert report["selected_count"] == 120
    assert report["selected_existing_overlap_count"] == 0
    assert [row["selected_count"] for row in report["source_statistics"]] == [40, 40, 40]
    assert report["selected_with_surface_signal_count"] == 107
    assert report["uses_detector_predictions"] is False
    assert report["uses_upstream_labels"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_prepare_review_queue_excludes_finalized_cases_and_caps_annotation_batch(
    tmp_path: Path,
) -> None:
    corpus = _corpus()
    corpus["cases"] = [copy.deepcopy(case) for _ in range(100) for case in corpus["cases"]]
    for index, case in enumerate(corpus["cases"]):
        case["id"] = f"case-{index:04d}"
    corpus_path = _write_json(tmp_path / "corpus.json", corpus)

    result = prepare_review_queue(
        corpus_path,
        queue_id="unit-queue-v1",
        corpus_id="unit-review-queue-v1",
        limit=500,
    )

    assert len(result.corpus["cases"]) == 500
    assert all(case["label"] == "review" for case in result.corpus["cases"])


def test_prepare_review_queue_rejects_limit_above_annotation_contract(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())

    with pytest.raises(ReviewQueueError, match="between 1 and 500"):
        prepare_review_queue(
            corpus_path,
            queue_id="unit-queue-v1",
            corpus_id="unit-review-queue-v1",
            limit=501,
        )


def test_prepare_review_queue_excludes_prior_queue_without_overlap(tmp_path: Path) -> None:
    source = _corpus()
    corpus_path = _write_json(tmp_path / "corpus.json", source)
    prior_path = _write_json(
        tmp_path / "prior.json",
        {
            "schema_version": 1,
            "corpus_id": "unit-prior-queue",
            "cases": copy.deepcopy(source["cases"][:2]),
        },
    )

    result = prepare_review_queue(
        corpus_path,
        queue_id="unit-queue-v2",
        corpus_id="unit-review-queue-v2",
        limit=4,
        exclude_corpus_paths=[prior_path],
    )

    prior_ids = {case["id"] for case in source["cases"][:2]}
    selected_ids = {case["id"] for case in result.corpus["cases"]}
    assert selected_ids.isdisjoint(prior_ids)
    assert len(selected_ids) == 4
    assert result.report["available_review_count"] == 6
    assert result.report["excluded_case_count"] == 2
    assert result.report["eligible_review_count"] == 4
    assert result.report["selected_existing_overlap_count"] == 0


def test_prepare_review_queue_excludes_prior_annotation_batch_without_overlap(
    tmp_path: Path,
) -> None:
    source = _corpus()
    corpus_path = _write_json(tmp_path / "corpus.json", source)
    prior_path = _write_json(
        tmp_path / "prior-annotations.json",
        _annotation_batch(source, source["cases"][:2]),
    )

    result = prepare_review_queue(
        corpus_path,
        queue_id="unit-queue-v2",
        corpus_id="unit-review-queue-v2",
        limit=4,
        exclude_annotation_batch_paths=[prior_path],
    )

    prior_ids = {case["id"] for case in source["cases"][:2]}
    selected_ids = {case["id"] for case in result.corpus["cases"]}
    assert selected_ids.isdisjoint(prior_ids)
    assert len(selected_ids) == 4
    assert result.report["excluded_case_count"] == 2
    assert result.report["excluded_annotation_case_count"] == 2
    assert result.report["excluded_review_case_count"] == 2
    assert result.report["selected_existing_overlap_count"] == 0


def test_prepare_review_queue_unions_cross_format_exclusions_and_reports_overlap(
    tmp_path: Path,
) -> None:
    source = _corpus()
    corpus_path = _write_json(tmp_path / "corpus.json", source)
    prior_corpus_path = _write_json(
        tmp_path / "prior.json",
        {
            "schema_version": 1,
            "corpus_id": "unit-prior-queue",
            "cases": copy.deepcopy(source["cases"][:2]),
        },
    )
    prior_annotations_path = _write_json(
        tmp_path / "prior-annotations.json",
        _annotation_batch(source, source["cases"][1:3]),
    )

    result = prepare_review_queue(
        corpus_path,
        queue_id="unit-queue-v2",
        corpus_id="unit-review-queue-v2",
        limit=3,
        exclude_corpus_paths=[prior_corpus_path],
        exclude_annotation_batch_paths=[prior_annotations_path],
    )

    assert result.report["excluded_case_count"] == 3
    assert result.report["excluded_input_overlap_count"] == 1
    assert result.report["selected_existing_overlap_count"] == 0


@pytest.mark.parametrize("change", ["wrong-corpus", "unknown-id", "changed-text"])
def test_prepare_review_queue_rejects_annotation_batch_not_matching_source(
    tmp_path: Path,
    change: str,
) -> None:
    source = _corpus()
    batch = _annotation_batch(source, source["cases"][:1])
    if change == "wrong-corpus":
        batch["corpus_id"] = "another-corpus"
    elif change == "unknown-id":
        batch["cases"][0]["case_id"] = "unknown-case"
    else:
        batch["cases"][0]["text"] = "변조된 원문"
    corpus_path = _write_json(tmp_path / "corpus.json", source)
    prior_path = _write_json(tmp_path / "prior-annotations.json", batch)

    with pytest.raises(ReviewQueueError, match="annotation exclusion does not match source corpus"):
        prepare_review_queue(
            corpus_path,
            queue_id="unit-queue-v2",
            corpus_id="unit-review-queue-v2",
            exclude_annotation_batch_paths=[prior_path],
        )


@pytest.mark.parametrize("change", ["unknown-id", "changed-text"])
def test_prepare_review_queue_rejects_exclusion_not_matching_source(
    tmp_path: Path,
    change: str,
) -> None:
    source = _corpus()
    excluded_case = copy.deepcopy(source["cases"][0])
    if change == "unknown-id":
        excluded_case["id"] = "unknown-case"
    else:
        excluded_case["text"] = "변조된 원문"
    corpus_path = _write_json(tmp_path / "corpus.json", source)
    prior_path = _write_json(
        tmp_path / "prior.json",
        {
            "schema_version": 1,
            "corpus_id": "unit-prior-queue",
            "cases": [excluded_case],
        },
    )

    with pytest.raises(ReviewQueueError, match="exclusion corpus does not match source corpus"):
        prepare_review_queue(
            corpus_path,
            queue_id="unit-queue-v2",
            corpus_id="unit-review-queue-v2",
            exclude_corpus_paths=[prior_path],
        )


def test_review_queue_cli_prints_only_aggregate_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    output_path = tmp_path / "protected.json"
    report_path = tmp_path / "aggregate.json"

    exit_code = main(
        [
            str(corpus_path),
            "--queue-id",
            "unit-queue-v1",
            "--corpus-id",
            "unit-review-queue-v1",
            "--limit",
            "5",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "available=6; excluded=0; eligible=6; selected=5" in captured.out
    assert captured.err == ""
    for forbidden in ("case-a", "원문 A", "text", "case_id"):
        assert forbidden not in captured.out
        assert forbidden not in report_path.read_text(encoding="utf-8")


def test_review_queue_cli_accepts_annotation_batch_exclusion(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = _corpus()
    corpus_path = _write_json(tmp_path / "corpus.json", source)
    prior_path = _write_json(
        tmp_path / "prior-annotations.json",
        _annotation_batch(source, source["cases"][:2]),
    )
    output_path = tmp_path / "protected.json"
    report_path = tmp_path / "aggregate.json"

    exit_code = main(
        [
            str(corpus_path),
            "--queue-id",
            "unit-queue-v2",
            "--corpus-id",
            "unit-review-queue-v2",
            "--limit",
            "4",
            "--exclude-annotation-batch",
            str(prior_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "available=6; excluded=2; eligible=4; selected=4" in captured.out
    assert captured.err == ""


def _corpus() -> dict[str, Any]:
    cases = [
        _case("case-a", "원문 A", "Source A"),
        _case("case-b", "원문 B", "Source A"),
        _case("case-c", "원문 C", "Source A"),
        _case("case-d", "원문 D", "Source B"),
        _case("case-e", "원문 E", "Source B"),
        _case("case-f", "원문 F", "Source B"),
    ]
    cases.append(
        {
            **_case("finalized", "확정 원문", "Source A"),
            "label": "hard-negative",
            "slices": ["direct"],
            "notes": "Already finalized.",
        }
    )
    return {"schema_version": 1, "corpus_id": "unit-source", "cases": cases}


def _case(case_id: str, text: str, source_name: str) -> dict[str, Any]:
    return {
        "id": case_id,
        "text": text,
        "label": "review",
        "expected_matches": [],
        "slices": ["unadjudicated-intake"],
        "source": {
            "kind": "curated",
            "name": source_name,
            "reference": None,
            "revision": "unit",
            "redistribution_allowed": True,
        },
        "license": "MIT",
        "split": "tuning",
        "notes": "Pending.",
    }


def _annotation_batch(source: dict[str, Any], cases: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "annotation_set_id": "unit-prior-annotations",
        "reviewer_id": "opaque-reviewer",
        "corpus_id": source["corpus_id"],
        "corpus_sha256": "0" * 64,
        "cases": [
            {
                "case_id": case["id"],
                "text": case["text"],
                "privacy_status": "approved",
                "label": "review",
                "expected_matches": [],
                "slices": ["unadjudicated-intake"],
                "notes": "Prior review.",
            }
            for case in cases
        ],
    }


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
