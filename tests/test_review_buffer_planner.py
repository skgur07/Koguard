"""Contract tests for the PF-005 incremental hard-negative review buffer."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

import pytest
from evaluation.corpus_validator import validate_corpus_paths
from evaluation.review_buffer_planner import (
    BUFFER_CONFIG_SCHEMA_PATH,
    BUFFER_REPORT_SCHEMA_PATH,
    ReviewBufferError,
    build_review_buffer,
    main,
)

_CHECKED_CONFIG_PATH = Path("evaluation/compositions/pf005-hard-negative-buffer.v1.json")
_CHECKED_REPORT_PATH = Path("evaluation/results/pf005-hard-negative-buffer-v1.report.json")


def test_buffer_selects_only_incremental_disjoint_review_cases(tmp_path: Path) -> None:
    first = _write_corpus(tmp_path / "first-expanded.json", "first-expanded", "first", 6)
    first_old = _write_corpus(
        tmp_path / "first-old.json", "first-old", "first", 2, texts=["first-0", "first-1"]
    )
    second = _write_corpus(tmp_path / "second-expanded.json", "second-expanded", "second", 6)
    second_old = _write_corpus(
        tmp_path / "second-old.json", "second-old", "second", 2, texts=["second-0", "second-1"]
    )
    config = _write_config(
        tmp_path,
        [
            ("first", first, "first-expanded", first_old, "first-old", 2),
            ("second", second, "second-expanded", second_old, "second-old", 2),
        ],
        max_source_share=0.5,
    )
    output = tmp_path / "buffer.json"
    report = tmp_path / "buffer.report.json"

    first_result = build_review_buffer(config, output_path=output, report_path=report)
    second_result = build_review_buffer(config)

    assert first_result == second_result
    assert len(first_result.corpus["cases"]) == 4
    old_texts = {"first-0", "first-1", "second-0", "second-1"}
    assert old_texts.isdisjoint(case["text"] for case in first_result.corpus["cases"])
    assert all(case["label"] == "review" for case in first_result.corpus["cases"])
    assert first_result.report["source_statistics"] == [
        {
            "source_id": "first",
            "available_count": 6,
            "existing_excluded_count": 2,
            "duplicate_excluded_count": 0,
            "eligible_count": 4,
            "selected_count": 2,
            "share": 0.5,
        },
        {
            "source_id": "second",
            "available_count": 6,
            "existing_excluded_count": 2,
            "duplicate_excluded_count": 0,
            "eligible_count": 4,
            "selected_count": 2,
            "share": 0.5,
        },
    ]
    assert first_result.report["selection_uses_upstream_labels_for_targeting"] is True
    assert first_result.report["upstream_labels_are_gold"] is False
    assert first_result.report["selected_existing_overlap_count"] == 0
    assert validate_corpus_paths([output]).review_case_count == 4


def test_buffer_excludes_nfkc_casefold_overlap(tmp_path: Path) -> None:
    expanded = _write_corpus(
        tmp_path / "expanded.json",
        "expanded",
        "source",
        3,
        texts=["ＡＢＣ", "새 문장", "다른 문장"],
    )
    old = _write_corpus(tmp_path / "old.json", "old", "source", 1, texts=["abc"])
    config = _write_config(
        tmp_path,
        [("source", expanded, "expanded", old, "old", 2)],
        max_source_share=1.0,
    )

    result = build_review_buffer(config)

    normalized = {
        unicodedata.normalize("NFKC", case["text"]).casefold() for case in result.corpus["cases"]
    }
    assert "abc" not in normalized
    assert result.report["source_statistics"][0]["existing_excluded_count"] == 1


def test_buffer_excludes_overlap_with_another_sources_existing_intake(tmp_path: Path) -> None:
    first = _write_corpus(
        tmp_path / "first-expanded.json",
        "first-expanded",
        "first",
        3,
        texts=["second-old", "first-new-a", "first-new-b"],
    )
    first_old = _write_corpus(tmp_path / "first-old.json", "first-old", "first", 1)
    second = _write_corpus(
        tmp_path / "second-expanded.json",
        "second-expanded",
        "second",
        2,
        texts=["second-old", "second-new"],
    )
    second_old = _write_corpus(
        tmp_path / "second-old.json", "second-old-corpus", "second", 1, texts=["second-old"]
    )
    config = _write_config(
        tmp_path,
        [
            ("first", first, "first-expanded", first_old, "first-old", 2),
            (
                "second",
                second,
                "second-expanded",
                second_old,
                "second-old-corpus",
                1,
            ),
        ],
        max_source_share=2 / 3,
    )

    result = build_review_buffer(config)

    assert "second-old" not in {case["text"] for case in result.corpus["cases"]}
    assert result.report["selected_existing_overlap_count"] == 0


def test_buffer_rejects_insufficient_incremental_cases(tmp_path: Path) -> None:
    expanded = _write_corpus(tmp_path / "expanded.json", "expanded", "source", 2)
    old = _write_corpus(tmp_path / "old.json", "old", "source", 2)
    config = _write_config(
        tmp_path,
        [("source", expanded, "expanded", old, "old", 1)],
        max_source_share=1.0,
    )

    with pytest.raises(ReviewBufferError, match="insufficient incremental"):
        build_review_buffer(config)


def test_buffer_schemas_are_versioned_and_closed() -> None:
    config = json.loads(BUFFER_CONFIG_SCHEMA_PATH.read_text(encoding="utf-8"))
    report = json.loads(BUFFER_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert config["properties"]["schema_version"]["const"] == 1
    assert config["additionalProperties"] is False
    assert config["$defs"]["source"]["additionalProperties"] is False
    assert report["properties"]["schema_version"]["const"] == 1
    assert report["additionalProperties"] is False


def test_buffer_cli_is_aggregate_only(tmp_path: Path, capsys: Any) -> None:
    expanded = _write_corpus(tmp_path / "expanded.json", "expanded", "source", 2)
    old = _write_corpus(tmp_path / "old.json", "old", "source", 1)
    config = _write_config(
        tmp_path,
        [("source", expanded, "expanded", old, "old", 1)],
        max_source_share=1.0,
    )
    output = tmp_path / "buffer.json"
    report = tmp_path / "buffer.report.json"

    exit_code = main([str(config), "--output", str(output), "--report", str(report)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "selected=1; maximum_source_share=1.000; gold_ready=false\n"
    assert captured.err == ""
    assert "source-1" not in captured.out


def test_checked_pf005_buffer_is_disjoint_balanced_and_review_only() -> None:
    config = json.loads(_CHECKED_CONFIG_PATH.read_text(encoding="utf-8"))
    report = json.loads(_CHECKED_REPORT_PATH.read_text(encoding="utf-8"))

    assert [source["quota"] for source in config["sources"]] == [300, 300, 300, 100]
    assert report["selected_count"] == 1000
    assert [source["selected_count"] for source in report["source_statistics"]] == [
        300,
        300,
        300,
        100,
    ]
    assert [source["existing_excluded_count"] for source in report["source_statistics"]] == [
        2500,
        750,
        750,
        0,
    ]
    assert report["maximum_observed_source_share"] == 0.3
    assert report["source_bias_gate_passed"] is True
    assert report["selected_existing_overlap_count"] == 0
    assert report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": 1000,
    }
    assert report["upstream_labels_are_gold"] is False
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def _write_corpus(
    path: Path,
    corpus_id: str,
    source_id: str,
    count: int,
    *,
    texts: list[str] | None = None,
) -> Path:
    resolved = texts or [f"{source_id}-{index}" for index in range(count)]
    payload = {
        "schema_version": 1,
        "corpus_id": corpus_id,
        "cases": [
            {
                "id": f"{source_id}-{index}",
                "text": text,
                "label": "review",
                "expected_matches": [],
                "slices": ["unadjudicated-intake"],
                "source": {
                    "kind": "licensed",
                    "name": source_id,
                    "reference": "https://example.invalid/source",
                    "revision": "unit",
                    "redistribution_allowed": True,
                },
                "license": "MIT",
                "split": "tuning",
                "notes": "Unadjudicated unit intake.",
            }
            for index, text in enumerate(resolved)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_config(
    tmp_path: Path,
    sources: list[tuple[str, Path, str, Path, str, int]],
    *,
    max_source_share: float,
) -> Path:
    payload = {
        "schema_version": 1,
        "buffer_id": "unit-review-buffer",
        "corpus_id": "unit-review-buffer",
        "split": "tuning",
        "selection": "incremental-source-sha256-v1",
        "max_source_share": max_source_share,
        "selection_uses_upstream_labels_for_targeting": True,
        "sources": [
            {
                "source_id": source_id,
                "corpus_path": source_path.name,
                "expected_corpus_id": corpus_id,
                "existing_corpus_path": existing_path.name,
                "expected_existing_corpus_id": existing_id,
                "quota": quota,
            }
            for source_id, source_path, corpus_id, existing_path, existing_id, quota in sources
        ],
    }
    path = tmp_path / "buffer-config.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path
