"""PF-007 false-negative candidate evaluation contract tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evaluation.fn_candidate_evaluation import (
    FN_CANDIDATE_REPORT_SCHEMA_PATH,
    evaluate_fn_candidates,
    main,
)

_PUBLISHED_REPORT_PATH = (
    Path(__file__).parents[1] / "evaluation" / "results" / "pf007-top-candidates.report.json"
)
_PUBLISHED_BALANCED_BATCH_REPORT_PATH = (
    Path(__file__).parents[1]
    / "evaluation"
    / "results"
    / "pf007-balanced-batch-001-candidates.report.json"
)


def test_schema_is_versioned_closed_and_aggregate_only() -> None:
    schema = json.loads(FN_CANDIDATE_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["candidateResult"]["additionalProperties"] is False
    serialized = json.dumps(schema)
    for forbidden in ("surface", "canonical_term", "case_id", "text"):
        assert f'"{forbidden}"' not in serialized


def test_candidate_evaluation_reports_incremental_metrics_without_raw_terms(
    tmp_path: Path,
) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    manifest_path = _write_json(tmp_path / "manifest.json", _manifest())

    report = evaluate_fn_candidates(corpus_path, manifest_path)

    assert len(report["inputs"]["corpus_sha256"]) == 64
    assert len(report["inputs"]["candidate_manifest_sha256"]) == 64
    assert report["corpus"] == {
        "case_count": 5,
        "positive_count": 3,
        "hard_negative_count": 2,
        "excluded_review_count": 1,
    }
    assert report["baseline"]["sentence_counts"] == {
        "tp": 0,
        "fp": 0,
        "fn": 3,
        "tn": 2,
    }
    assert report["baseline"]["occurrence_counts"] == {"tp": 0, "fp": 0, "fn": 3}
    assert report["combined_candidate"]["sentence_counts"] == {
        "tp": 2,
        "fp": 0,
        "fn": 1,
        "tn": 2,
    }
    assert report["combined_candidate"]["sentence_delta"] == {
        "tp": 2,
        "fp": 0,
        "fn": -2,
        "tn": 0,
    }
    assert report["combined_candidate"]["occurrence_counts"] == {
        "tp": 2,
        "fp": 0,
        "fn": 1,
    }
    assert report["combined_candidate"]["occurrence_delta"] == {
        "tp": 2,
        "fp": 0,
        "fn": -2,
    }
    assert report["combined_candidate"]["positive_case_support"] == 2
    assert report["combined_candidate"]["hard_negative_case_support"] == 2
    assert report["combined_candidate"]["tuning_gate_passed"] is True
    assert report["candidates"] == [
        {
            "candidate_id": "candidate.term-a",
            "positive_case_support": 1,
            "hard_negative_case_support": 2,
            "sentence_tp_delta": 1,
            "sentence_fp_delta": 0,
            "occurrence_tp_delta": 1,
            "occurrence_fp_delta": 0,
            "tuning_gate_passed": True,
        },
        {
            "candidate_id": "candidate.term-b",
            "positive_case_support": 1,
            "hard_negative_case_support": 2,
            "sentence_tp_delta": 1,
            "sentence_fp_delta": 0,
            "occurrence_tp_delta": 1,
            "occurrence_fp_delta": 0,
            "tuning_gate_passed": True,
        },
    ]
    serialized = json.dumps(report, ensure_ascii=False)
    for raw_value in ("가나다라마", "바사아자차", "숨긴 검토 원문"):
        assert raw_value not in serialized


def test_published_report_and_cli_expose_only_aggregate_candidate_ids(
    tmp_path: Path,
    capsys: Any,
) -> None:
    published = json.loads(_PUBLISHED_REPORT_PATH.read_text(encoding="utf-8"))
    assert published["combined_candidate"]["sentence_delta"] == {
        "tp": 10,
        "fp": 0,
        "fn": -10,
        "tn": 0,
    }
    assert sum(item["tuning_gate_passed"] for item in published["candidates"]) == 5

    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    manifest_path = _write_json(tmp_path / "manifest.json", _manifest())
    output_path = tmp_path / "report.json"
    exit_code = main([str(corpus_path), str(manifest_path), "--output", str(output_path)])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "candidates=2" in captured.out
    assert "sentence_tp_delta=2" in captured.out
    for raw_value in ("가나다라마", "바사아자차", "숨긴 검토 원문"):
        assert raw_value not in captured.out
        assert raw_value not in output_path.read_text(encoding="utf-8")
    assert captured.err == ""


def test_published_balanced_batch_candidate_report_is_aggregate_only() -> None:
    report = json.loads(_PUBLISHED_BALANCED_BATCH_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["corpus"] == {
        "case_count": 536,
        "positive_count": 264,
        "hard_negative_count": 272,
        "excluded_review_count": 1964,
    }
    assert report["combined_candidate"]["sentence_delta"] == {
        "tp": 0,
        "fp": 0,
        "fn": 0,
        "tn": 0,
    }
    assert report["combined_candidate"]["occurrence_delta"] == {
        "tp": 2,
        "fp": -2,
        "fn": -2,
    }
    assert report["combined_candidate"]["tuning_gate_passed"] is True
    assert report["candidates"] == [
        {
            "candidate_id": "core.literal.pf007.007",
            "positive_case_support": 3,
            "hard_negative_case_support": 272,
            "sentence_tp_delta": 0,
            "sentence_fp_delta": 0,
            "occurrence_tp_delta": 2,
            "occurrence_fp_delta": -2,
            "tuning_gate_passed": True,
        }
    ]
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("surface", "canonical_term", "case_id", "text"):
        assert f'"{forbidden}"' not in serialized


def test_cli_refuses_to_overwrite_an_input(tmp_path: Path, capsys: Any) -> None:
    corpus_path = _write_json(tmp_path / "corpus.json", _corpus())
    manifest_path = _write_json(tmp_path / "manifest.json", _manifest())
    original = corpus_path.read_bytes()

    exit_code = main([str(corpus_path), str(manifest_path), "--output", str(corpus_path)])

    assert exit_code == 1
    assert corpus_path.read_bytes() == original
    assert "output must not overwrite an input" in capsys.readouterr().err


def test_input_hashes_are_stable_across_lf_and_crlf(tmp_path: Path) -> None:
    corpus = (json.dumps(_corpus(), ensure_ascii=False, indent=2) + "\n").encode()
    manifest = (json.dumps(_manifest(), ensure_ascii=False, indent=2) + "\n").encode()
    lf_corpus = tmp_path / "lf-corpus.json"
    crlf_corpus = tmp_path / "crlf-corpus.json"
    lf_manifest = tmp_path / "lf-manifest.json"
    crlf_manifest = tmp_path / "crlf-manifest.json"
    lf_corpus.write_bytes(corpus)
    crlf_corpus.write_bytes(corpus.replace(b"\n", b"\r\n"))
    lf_manifest.write_bytes(manifest)
    crlf_manifest.write_bytes(manifest.replace(b"\n", b"\r\n"))

    lf_inputs = evaluate_fn_candidates(lf_corpus, lf_manifest)["inputs"]
    crlf_inputs = evaluate_fn_candidates(crlf_corpus, crlf_manifest)["inputs"]

    assert lf_inputs == crlf_inputs


def _manifest() -> dict[str, Any]:
    source = {
        "source_id": "unit-source",
        "kind": "curated",
        "name": "Unit source",
        "reference": None,
        "revision": "unit",
        "license": "MIT",
        "license_status": "approved",
        "redistribution_allowed": True,
    }

    def candidate(candidate_id: str, surface: str) -> dict[str, Any]:
        return {
            "candidate_id": candidate_id,
            "surface": surface,
            "normalized_surface": surface,
            "canonical": surface,
            "normalized_canonical": surface,
            "representation": "literal",
            "matcher": "exact",
            "target_layer": "core",
            "classification": "positive",
            "status": "candidate",
            "source_id": "unit-source",
            "evaluation_refs": [],
            "review": {
                "status": "approved",
                "decision_reference": "unit consensus",
                "notes": "Unit candidate.",
            },
            "notes": "Unit candidate.",
        }

    return {
        "schema_version": 1,
        "manifest_id": "unit-candidates",
        "normalization_form": "NFKC",
        "sources": [source],
        "candidates": [
            candidate("candidate.term-a", "가나다라마"),
            candidate("candidate.term-b", "바사아자차"),
        ],
    }


def _corpus() -> dict[str, Any]:
    source = {
        "kind": "curated",
        "name": "Unit corpus",
        "reference": None,
        "revision": "unit",
        "redistribution_allowed": True,
    }

    def case(
        case_id: str,
        text: str,
        label: str,
        matches: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "id": case_id,
            "text": text,
            "label": label,
            "expected_matches": matches,
            "slices": ["direct"] if label == "positive" else ["benign-substring"],
            "source": source,
            "license": "MIT",
            "split": "tuning",
            "notes": "Unit case.",
        }

    return {
        "schema_version": 1,
        "corpus_id": "unit-fn-candidates",
        "cases": [
            case("positive-a", "가나다라마", "positive", [_match(0, 5, "가나다라마")]),
            case("positive-b", "바사아자차", "positive", [_match(0, 5, "바사아자차")]),
            case("positive-other", "미등록", "positive", [_match(0, 3, "미등록")]),
            case("negative-a", "오늘 날씨가 맑습니다", "hard-negative", []),
            case("negative-b", "회의 자료를 검토합니다", "hard-negative", []),
            {
                **case("review", "숨긴 검토 원문", "hard-negative", []),
                "label": "review",
                "slices": ["unadjudicated-intake"],
            },
        ],
    }


def _match(start: int, end: int, canonical: str) -> dict[str, Any]:
    return {"start": start, "end": end, "canonical_term": canonical}


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
