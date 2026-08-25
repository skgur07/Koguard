"""Contract tests for blinded re-audit preparation and application."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.reaudit_workflow import (
    ReauditWorkflowError,
    apply_reaudit_corpus,
    main,
    prepare_matcher_fp_reaudit,
)

_PUBLISHED_POLICY_REAUDIT_APPLY_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf005-policy-reaudit-v1-apply.report.json"
)


def test_prepare_matcher_fp_reaudit_blinds_prior_decisions_and_is_aggregate_only(
    tmp_path: Path,
) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    report_path = _write_json(tmp_path / "ablation.json", _ablation(corpus_path))

    first = prepare_matcher_fp_reaudit(
        corpus_path,
        report_path,
        matcher="choseong",
        corpus_id="unit-choseong-reaudit-v1",
    )
    second = prepare_matcher_fp_reaudit(
        corpus_path,
        report_path,
        matcher="choseong",
        corpus_id="unit-choseong-reaudit-v1",
    )

    assert first == second
    assert [case["id"] for case in first.corpus["cases"]] == ["case-a", "case-b"]
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert all(case["expected_matches"] == [] for case in first.corpus["cases"])
    assert all(case["slices"] == ["unadjudicated-intake"] for case in first.corpus["cases"])
    assert first.report["selected_count"] == 2
    assert first.report["prior_label_counts"] == {
        "positive": 1,
        "hard-negative": 1,
        "review": 0,
    }
    serialized = json.dumps(first.report, ensure_ascii=False)
    for forbidden in ("case-a", "case-b", "보호 원문", "canonical_term"):
        assert forbidden not in serialized


def test_prepare_matcher_fp_reaudit_rejects_mismatched_corpus_evidence(tmp_path: Path) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    payload = _ablation(corpus_path)
    payload["corpus"]["sha256"] = "0" * 64
    report_path = _write_json(tmp_path / "ablation.json", payload)

    with pytest.raises(ReauditWorkflowError, match="corpus evidence mismatch"):
        prepare_matcher_fp_reaudit(
            corpus_path,
            report_path,
            matcher="choseong",
            corpus_id="unit-choseong-reaudit-v1",
        )


def test_prepare_cli_prints_only_aggregate_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    ablation_path = _write_json(tmp_path / "ablation.json", _ablation(corpus_path))
    output_path = tmp_path / "protected.json"
    report_path = tmp_path / "aggregate.json"

    exit_code = main(
        [
            "prepare",
            str(corpus_path),
            str(ablation_path),
            "--matcher",
            "choseong",
            "--corpus-id",
            "unit-choseong-reaudit-v1",
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "selected=2" in captured.out
    assert captured.err == ""
    for forbidden in ("case-a", "case-b", "보호 원문", "canonical_term"):
        assert forbidden not in captured.out
        assert forbidden not in report_path.read_text(encoding="utf-8")


def test_apply_reaudit_corpus_replaces_only_decisions_and_reports_aggregates(
    tmp_path: Path,
) -> None:
    source = _corpus()
    source_path = _write_json(tmp_path / "source.json", source)
    prepared_path = _prepare_reaudit(tmp_path, source_path)
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    reaudit = {
        "schema_version": 1,
        "corpus_id": "unit-choseong-reaudit-v1",
        "cases": [
            {
                **prepared["cases"][0],
                "label": "positive",
                "expected_matches": [{"start": 0, "end": 2, "canonical_term": "대표어"}],
                "slices": ["choseong", "domain-term"],
                "notes": "Independent re-audit consensus.",
            },
            {
                **prepared["cases"][1],
                "label": "review",
                "expected_matches": [],
                "slices": ["unadjudicated-intake"],
                "notes": "Re-audit remained unresolved.",
            },
        ],
    }
    reaudit_path = _write_json(tmp_path / "reaudit.json", reaudit)
    adjudication_report_path = _write_adjudication_report(tmp_path, prepared_path, reaudit)

    result = apply_reaudit_corpus(
        source_path,
        prepared_path,
        reaudit_path,
        adjudication_report_path,
    )

    by_id = {case["id"]: case for case in result.corpus["cases"]}
    assert by_id["case-a"]["label"] == "positive"
    assert by_id["case-a"]["source"] == source["cases"][0]["source"]
    assert by_id["case-b"]["label"] == "review"
    assert by_id["case-c"] == source["cases"][2]
    assert result.report["applied_count"] == 2
    assert result.report["updated_corpus_counts"] == {
        "positive": 1,
        "hard-negative": 1,
        "review": 1,
    }
    serialized = json.dumps(result.report, ensure_ascii=False)
    for forbidden in ("case-a", "case-b", "보호 원문", "canonical_term"):
        assert forbidden not in serialized


def test_apply_reaudit_corpus_rejects_modified_source_text(tmp_path: Path) -> None:
    source = _corpus()
    source_path = _write_json(tmp_path / "source.json", source)
    prepared_path = _prepare_reaudit(tmp_path, source_path)
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    changed: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": "unit-choseong-reaudit-v1",
        "cases": [prepared["cases"][0], prepared["cases"][1]],
    }
    changed["cases"][0] = {**changed["cases"][0], "text": "변조된 원문"}
    reaudit_path = _write_json(tmp_path / "reaudit.json", changed)
    adjudication_report_path = _write_adjudication_report(tmp_path, prepared_path, changed)

    with pytest.raises(ReauditWorkflowError, match="immutable case fields"):
        apply_reaudit_corpus(
            source_path,
            prepared_path,
            reaudit_path,
            adjudication_report_path,
        )


def test_apply_reaudit_corpus_rejects_unbound_adjudication_report(tmp_path: Path) -> None:
    source_path = _write_json(tmp_path / "source.json", _corpus())
    prepared_path = _prepare_reaudit(tmp_path, source_path)
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    adjudicated_path = _write_json(tmp_path / "adjudicated.json", prepared)
    report_path = _write_adjudication_report(tmp_path, prepared_path, prepared)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["source_corpus_sha256"] = "0" * 64
    _write_json(report_path, report)

    with pytest.raises(ReauditWorkflowError, match="adjudication evidence mismatch"):
        apply_reaudit_corpus(
            source_path,
            prepared_path,
            adjudicated_path,
            report_path,
        )


def test_published_policy_reaudit_apply_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_POLICY_REAUDIT_APPLY_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["applied_count"] == 3
    assert report["source_corpus_counts"] == {
        "positive": 264,
        "hard-negative": 272,
        "review": 1964,
    }
    assert report["updated_corpus_counts"] == {
        "positive": 265,
        "hard-negative": 271,
        "review": 1964,
    }
    assert report["label_transition_counts"] == {
        "hard-negative->positive": 1,
        "positive->positive": 2,
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def _ablation(corpus_path: Path) -> dict[str, Any]:
    from evaluation.reaudit_workflow import canonical_corpus_sha256

    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    return {
        "schema_version": 1,
        "corpus": {
            "corpus_ids": [corpus["corpus_id"]],
            "sha256": canonical_corpus_sha256(corpus),
        },
        "matcher_ablation": [
            {
                "matcher": "choseong",
                "new_false_positive_case_ids": ["case-b", "case-a"],
            }
        ],
    }


def _prepare_reaudit(tmp_path: Path, source_path: Path) -> Path:
    ablation_path = _write_json(tmp_path / "ablation.json", _ablation(source_path))
    prepared_path = tmp_path / "prepared.json"
    prepare_matcher_fp_reaudit(
        source_path,
        ablation_path,
        matcher="choseong",
        corpus_id="unit-choseong-reaudit-v1",
        output_path=prepared_path,
    )
    return prepared_path


def _write_adjudication_report(
    tmp_path: Path,
    prepared_path: Path,
    adjudicated: dict[str, Any],
) -> Path:
    counts = {label: 0 for label in ("positive", "hard-negative", "review")}
    for case in adjudicated["cases"]:
        counts[case["label"]] += 1
    return _write_json(
        tmp_path / "adjudication-report.json",
        {
            "schema_version": 1,
            "corpus_id": adjudicated["corpus_id"],
            "source_corpus_sha256": hashlib.sha256(prepared_path.read_bytes()).hexdigest(),
            "batch_case_count": len(adjudicated["cases"]),
            "batch_counts": counts,
            "gold_ready": False,
        },
    )


def _corpus() -> dict[str, Any]:
    source = {
        "kind": "curated",
        "name": "Unit source",
        "reference": None,
        "revision": "unit",
        "redistribution_allowed": True,
    }
    return {
        "schema_version": 1,
        "corpus_id": "unit-source",
        "cases": [
            {
                "id": "case-a",
                "text": "보호 원문 A",
                "label": "hard-negative",
                "expected_matches": [],
                "slices": ["domain-term"],
                "source": source,
                "license": "MIT",
                "split": "tuning",
                "notes": "Prior negative.",
            },
            {
                "id": "case-b",
                "text": "보호 원문 B",
                "label": "positive",
                "expected_matches": [{"start": 0, "end": 2, "canonical_term": "기존어"}],
                "slices": ["direct"],
                "source": source,
                "license": "MIT",
                "split": "tuning",
                "notes": "Prior positive.",
            },
            {
                "id": "case-c",
                "text": "일반 문장",
                "label": "hard-negative",
                "expected_matches": [],
                "slices": ["direct"],
                "source": source,
                "license": "MIT",
                "split": "tuning",
                "notes": "Untouched.",
            },
        ],
    }


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
