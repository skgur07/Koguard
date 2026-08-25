"""Contract tests for deterministic source-balanced review queues."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.review_queue_planner import ReviewQueueError, main, prepare_review_queue


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
    assert "available=6; selected=5" in captured.out
    assert captured.err == ""
    for forbidden in ("case-a", "원문 A", "text", "case_id"):
        assert forbidden not in captured.out
        assert forbidden not in report_path.read_text(encoding="utf-8")


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


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
