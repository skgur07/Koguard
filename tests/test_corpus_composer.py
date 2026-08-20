"""Tests for the balanced multi-source PF-005 review composer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.corpus_composer import (
    COMPOSITION_REPORT_SCHEMA_PATH,
    COMPOSITION_SCHEMA_PATH,
    CorpusCompositionError,
    compose_review_intake,
    main,
)
from evaluation.corpus_validator import validate_corpus_paths

_CHECKED_CONFIG_PATH = Path("evaluation/compositions/pf005-balanced-review-intake.v1.json")
_CHECKED_REPORT_PATH = Path("evaluation/results/pf005-balanced-review-intake-v1.report.json")


def test_composer_selects_deterministic_disjoint_review_cases(tmp_path: Path) -> None:
    first_path = _write_corpus(tmp_path / "first.json", "first-corpus", "first", 4)
    second_path = _write_corpus(tmp_path / "second.json", "second-corpus", "second", 4)
    config_path = _write_config(
        tmp_path,
        sources=[
            ("first", first_path, "first-corpus", 2),
            ("second", second_path, "second-corpus", 2),
        ],
        max_source_share=0.5,
    )
    output_path = tmp_path / "composed.json"
    report_path = tmp_path / "composed.report.json"

    first = compose_review_intake(
        config_path,
        output_path=output_path,
        report_path=report_path,
    )
    second = compose_review_intake(config_path)

    assert first == second
    assert len(first.corpus["cases"]) == 4
    assert len({case["id"] for case in first.corpus["cases"]}) == 4
    assert all("first" not in case["id"] for case in first.corpus["cases"])
    assert all("second" not in case["id"] for case in first.corpus["cases"])
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert first.report["source_statistics"] == [
        {
            "source_id": "first",
            "available_count": 4,
            "selected_count": 2,
            "duplicate_excluded_count": 0,
            "share": 0.5,
        },
        {
            "source_id": "second",
            "available_count": 4,
            "selected_count": 2,
            "duplicate_excluded_count": 0,
            "share": 0.5,
        },
    ]
    assert first.report["source_bias_gate_passed"] is True
    assert validate_corpus_paths([output_path]).review_case_count == 4


def test_composer_skips_cross_source_normalized_duplicates(tmp_path: Path) -> None:
    first_path = _write_corpus(
        tmp_path / "first.json",
        "first-corpus",
        "first",
        1,
        texts=["중복 문장"],
    )
    second_path = _write_corpus(
        tmp_path / "second.json",
        "second-corpus",
        "second",
        3,
        texts=["중복 문장", "고유 문장 A", "고유 문장 B"],
    )
    config_path = _write_config(
        tmp_path,
        sources=[
            ("first", first_path, "first-corpus", 1),
            ("second", second_path, "second-corpus", 2),
        ],
        max_source_share=2 / 3,
    )

    result = compose_review_intake(config_path)

    assert result.report["selected_count"] == 3
    assert result.report["source_statistics"][1]["duplicate_excluded_count"] == 1
    assert len({case["text"] for case in result.corpus["cases"]}) == 3


def test_composer_prioritizes_and_preserves_finalized_cases(tmp_path: Path) -> None:
    source_path = _write_corpus(tmp_path / "source.json", "source-corpus", "source", 1)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["cases"][0]["label"] = "hard-negative"
    payload["cases"][0]["slices"] = ["direct"]
    source_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        sources=[("source", source_path, "source-corpus", 1)],
        max_source_share=1.0,
    )

    result = compose_review_intake(config_path)

    assert result.corpus["cases"][0]["label"] == "hard-negative"
    assert result.report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 1,
        "review": 0,
    }
    assert result.report["adjudication_quality"] == {
        "carried_finalized": 1,
        "pending_review": 0,
    }


def test_composer_rejects_non_redistributable_input(tmp_path: Path) -> None:
    source_path = _write_corpus(tmp_path / "source.json", "source-corpus", "source", 1)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    payload["cases"][0]["source"]["redistribution_allowed"] = False
    source_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    config_path = _write_config(
        tmp_path,
        sources=[("source", source_path, "source-corpus", 1)],
        max_source_share=1.0,
    )

    with pytest.raises(CorpusCompositionError, match="redistributable"):
        compose_review_intake(config_path)


def test_composition_schemas_are_versioned_and_closed() -> None:
    config_schema = json.loads(COMPOSITION_SCHEMA_PATH.read_text(encoding="utf-8"))
    report_schema = json.loads(COMPOSITION_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert config_schema["properties"]["schema_version"]["const"] == 1
    assert config_schema["additionalProperties"] is False
    assert config_schema["$defs"]["source"]["additionalProperties"] is False
    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["additionalProperties"] is False


def test_checked_pf005_composition_meets_source_share_gate() -> None:
    config = json.loads(_CHECKED_CONFIG_PATH.read_text(encoding="utf-8"))
    report = json.loads(_CHECKED_REPORT_PATH.read_text(encoding="utf-8"))

    assert [source["quota"] for source in config["sources"]] == [750, 750, 750, 250]
    assert report["selected_count"] == 2500
    assert [source["selected_count"] for source in report["source_statistics"]] == [
        750,
        750,
        750,
        250,
    ]
    assert report["maximum_observed_source_share"] == 0.3
    assert report["source_bias_gate_passed"] is True
    assert report["generated_label_counts"] == {
        "positive": 62,
        "hard-negative": 30,
        "review": 2408,
    }
    assert report["adjudication_quality"] == {
        "carried_finalized": 92,
        "pending_review": 2408,
    }
    assert report["gold_ready"] is False


def test_composer_cli_prints_aggregate_only(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_path = _write_corpus(tmp_path / "source.json", "source-corpus", "source", 1)
    config_path = _write_config(
        tmp_path,
        sources=[("source", source_path, "source-corpus", 1)],
        max_source_share=1.0,
    )
    output_path = tmp_path / "composed.json"
    report_path = tmp_path / "composed.report.json"

    exit_code = main(
        [
            str(config_path),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "selected=1; maximum_source_share=1.000; gold_ready=false\n"
    assert captured.err == ""


def _write_corpus(
    path: Path,
    corpus_id: str,
    source_id: str,
    count: int,
    *,
    texts: list[str] | None = None,
) -> Path:
    resolved_texts = texts or [f"{source_id} 문장 {index}" for index in range(count)]
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
                    "revision": "unit-revision",
                    "redistribution_allowed": True,
                },
                "license": "MIT",
                "split": "tuning",
                "notes": "Unadjudicated test intake.",
            }
            for index, text in enumerate(resolved_texts)
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def _write_config(
    tmp_path: Path,
    *,
    sources: list[tuple[str, Path, str, int]],
    max_source_share: float,
) -> Path:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "composition_id": "unit-balanced-review-intake",
        "corpus_id": "unit-balanced-review-intake",
        "split": "tuning",
        "selection": "stable-sha256-rank-v1",
        "max_source_share": max_source_share,
        "sources": [
            {
                "source_id": source_id,
                "corpus_path": path.name,
                "expected_corpus_id": corpus_id,
                "quota": quota,
            }
            for source_id, path, corpus_id, quota in sources
        ],
    }
    config_path = tmp_path / "composition.json"
    config_path.write_text(json.dumps(payload), encoding="utf-8")
    return config_path
