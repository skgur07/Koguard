"""Tests for privacy-safe PF-009 profile evaluation reports."""

import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.profile_report import ProfileReportError, build_profile_report, main

from koguard import KoguardEngine

_PUBLIC_REPORT = Path("evaluation/results/pf009-profile-evaluation.report.json")
_POSITIVE_SLICE_REPORT = Path(
    "evaluation/results/pf005-positive-slice-buffer-v1.profile.report.json"
)
_SLICE_COVERAGE_REPORT = Path("evaluation/results/pf005-slice-coverage.report.json")
_REPORT_SCHEMA = Path("evaluation/profile-report.schema.json")


def _settings(profile: str) -> dict[str, object]:
    config = KoguardEngine(profile=profile).config  # type: ignore[arg-type]
    return {
        "alias_matching": config.alias_matching,
        "choseong_matching": config.choseong_matching,
        "exact_matching": config.exact_matching,
        "fuzzy_matching": config.fuzzy_matching,
        "fuzzy_max_distance": config.fuzzy_max_distance,
        "fuzzy_max_index_entries": config.fuzzy_max_index_entries,
        "fuzzy_max_operations": config.fuzzy_max_operations,
        "fuzzy_max_term_length": config.fuzzy_max_term_length,
        "fuzzy_min_score": config.fuzzy_min_score,
        "fuzzy_min_term_length": config.fuzzy_min_term_length,
        "jamo_composition_matching": config.jamo_composition_matching,
        "keyboard_matching": config.keyboard_matching,
        "max_input_length": config.max_input_length,
        "max_whitespace_gap": config.max_whitespace_gap,
        "mixed_gap_matching": config.mixed_gap_matching,
        "obfuscation_separators": "".join(sorted(config.obfuscation_separators)),
        "repeat_reduction_threshold": config.repeat_reduction_threshold,
        "repeated_matching": config.repeated_matching,
        "segmented_input_matching": config.segmented_input_matching,
        "separator_matching": config.separator_matching,
        "unicode_form": config.unicode_form,
        "whitespace_gap_matching": config.whitespace_gap_matching,
    }


def _metrics(tp: int, fp: int, fn: int, tn: int | None = None) -> dict[str, object]:
    counts = {"tp": tp, "fp": fp, "fn": fn}
    if tn is not None:
        counts["tn"] = tn
    return {"counts": counts, "precision": 1.0, "recall": 0.5, "f1": 0.6}


def _source() -> dict[str, Any]:
    profiles = []
    for profile, source_id, sentence_tp, occurrence_tp, retained in (
        ("strict", "exact-alias", 3, 3, 70_000),
        ("balanced", "choseong", 4, 4, 108_000),
        ("aggressive", "all-enabled", 5, 4, 199_000),
    ):
        profiles.append(
            {
                "profile_id": source_id,
                "settings": _settings(profile),
                "sentence_metrics": _metrics(sentence_tp, 0, 5 - sentence_tp, 2),
                "occurrence_metrics": _metrics(occurrence_tp, 0, 5 - occurrence_tp),
                "performance": {
                    "short_chat": {"input_length": 15, "p50_ms": 0.02, "p95_ms": 0.05},
                    "maximum_input": {
                        "input_length": 4096,
                        "p50_ms": 5.0,
                        "p95_ms": 9.0,
                    },
                    "engine_retained_memory_bytes": retained,
                },
            }
        )
    return {
        "schema_version": 1,
        "measured_at": "2026-08-13T03:57:06+00:00",
        "corpus": {
            "sha256": "a" * 64,
            "case_count": 7,
            "positive_count": 5,
            "hard_negative_count": 2,
            "excluded_review_count": 1,
        },
        "environment": {
            "koguard_version": "0.1.0",
            "python_version": "3.11.9",
            "implementation": "CPython",
            "platform": "test-platform",
            "processor": "test-processor",
            "text": "must-not-leak",
        },
        "profiles": profiles,
        "case_results": [{"case_id": "must-not-leak", "text": "must-not-leak"}],
    }


def _all_keys(value: object) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for item in value.values() for key in _all_keys(item)}
    if isinstance(value, list):
        return {key for item in value for key in _all_keys(item)}
    return set()


def test_build_profile_report_maps_configs_and_omits_protected_case_data() -> None:
    source = _source()
    source["profiles"][0]["sentence_metrics"]["case_id"] = "must-not-leak"

    report = build_profile_report(source, source_sha256="b" * 64)

    assert [profile["profile"] for profile in report["profiles"]] == [
        "strict",
        "balanced",
        "aggressive",
    ]
    assert report["balanced_evidence"] == {
        "sentence_tp_delta_vs_strict": 1,
        "sentence_fp_delta_vs_strict": 0,
        "occurrence_tp_delta_vs_strict": 1,
        "occurrence_fp_delta_vs_strict": 0,
    }
    assert report["balanced_gates"]["passed"] is True
    assert report["limitations"][2] == (
        "hard-negative 2건에서 balanced 문장 FP 0건으로 측정됐으나 "
        "실서비스 전체 FP rate를 일반화할 수 없다."
    )
    assert _all_keys(report).isdisjoint(
        {"case_results", "case_id", "text", "canonical_term", "slice_metrics"}
    )


def test_committed_slice_coverage_report_is_aggregate_only() -> None:
    report = json.loads(_SLICE_COVERAGE_REPORT.read_text(encoding="utf-8"))

    assert report["targets"] == {
        "positive_per_slice": 30,
        "hard_negative_per_slice": 2,
    }
    assert report["balanced_choseong_increment"] == {
        "sentence_tp_delta_vs_strict": 24,
        "sentence_fp_delta_vs_strict": 0,
        "occurrence_tp_delta_vs_strict": 30,
        "occurrence_fp_delta_vs_strict": 2,
    }
    by_slice = {row["slice"]: row for row in report["slice_coverage"]}
    assert by_slice["choseong"] == {
        "slice": "choseong",
        "positive": 30,
        "hard_negative": 0,
        "positive_gap": 0,
        "hard_negative_gap": 2,
    }
    assert by_slice["separator"]["positive_gap"] == 27
    assert by_slice["whitespace"]["positive_gap"] == 28
    assert report["targeted_supplement"]["finalized_count"] == 89
    assert report["targeted_supplement"]["review_count"] == 31
    combined_by_slice = {row["slice"]: row for row in report["combined_slice_coverage"]}
    assert combined_by_slice["choseong"]["positive"] == 36
    assert combined_by_slice["repeated"]["hard_negative"] == 38
    assert combined_by_slice["separator"] == {
        "slice": "separator",
        "positive": 4,
        "hard_negative": 13,
        "positive_gap": 26,
        "hard_negative_gap": 0,
    }
    assert combined_by_slice["whitespace"]["hard_negative_gap"] == 0
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_build_profile_report_rejects_profile_settings_drift() -> None:
    source = _source()
    source["profiles"][1]["settings"]["fuzzy_matching"] = True

    with pytest.raises(ProfileReportError, match="does not match"):
        build_profile_report(source, source_sha256="b" * 64)


def test_profile_report_cli_refuses_to_overwrite_source(tmp_path: Path) -> None:
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(_source()), encoding="utf-8")

    assert main(["--source-ablation", str(source_path), "--output", str(source_path)]) == 1


def test_profile_report_schema_is_versioned_and_closed_at_the_root() -> None:
    schema = json.loads(_REPORT_SCHEMA.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"] == {"const": 1}


def test_committed_profile_report_is_aggregate_only_and_tracks_balanced_gates() -> None:
    report = json.loads(_PUBLIC_REPORT.read_text(encoding="utf-8"))

    assert report["schema_version"] == 1
    assert report["source"]["ablation_report_sha256"] == (
        "8e6feb87bd2293c69caef02492fa415072750d55a88de78b647fe8f15883851b"
    )
    assert report["source"]["corpus"] == {
        "classification": "independent-tuning-provisional",
        "sha256": "f499e1fa304a63a6dbc5eac102264d0997aa6caf41c7e4ffd30dadfd010e16b3",
        "case_count": 2763,
        "positive_count": 639,
        "hard_negative_count": 2124,
        "excluded_review_count": 737,
        "gold_ready": False,
    }
    assert report["balanced_evidence"] == {
        "sentence_tp_delta_vs_strict": 24,
        "sentence_fp_delta_vs_strict": 0,
        "occurrence_tp_delta_vs_strict": 30,
        "occurrence_fp_delta_vs_strict": 2,
    }
    assert report["balanced_gates"]["passed"] is False
    assert report["limitations"][:3] == [
        "다중 출처 intake 중 독립 검토로 확정된 2763건만 평가한 tuning 결과다.",
        "gold_ready가 아니며 737건은 review로 자동 평가에서 제외됐다.",
        "hard-negative 2124건에서 balanced 문장 FP 0건으로 측정됐으나 "
        "실서비스 전체 FP rate를 일반화할 수 없다.",
    ]
    assert {profile["profile"]: profile["settings"] for profile in report["profiles"]} == {
        profile: _settings(profile) for profile in ("strict", "balanced", "aggressive")
    }
    assert _all_keys(report).isdisjoint(
        {"case_results", "case_id", "text", "canonical_term", "slice_metrics"}
    )


def test_positive_slice_profile_report_is_aggregate_only() -> None:
    report = json.loads(_POSITIVE_SLICE_REPORT.read_text(encoding="utf-8"))

    assert report["source"]["corpus"] == {
        "classification": "independent-tuning-provisional",
        "sha256": "fbab31118b12a72e9c4fc73f88699b0bb3fed677c3d8a7dca863f5ac995fbf7d",
        "case_count": 480,
        "positive_count": 240,
        "hard_negative_count": 240,
        "excluded_review_count": 0,
        "gold_ready": False,
    }
    by_profile = {item["profile"]: item for item in report["profiles"]}
    assert by_profile["strict"]["sentence_metrics"]["counts"] == {
        "tp": 63,
        "fp": 0,
        "fn": 177,
        "tn": 240,
    }
    assert by_profile["balanced"]["occurrence_metrics"]["counts"] == {
        "tp": 63,
        "fp": 0,
        "fn": 177,
    }
    assert by_profile["aggressive"]["sentence_metrics"]["counts"] == {
        "tp": 240,
        "fp": 0,
        "fn": 0,
        "tn": 240,
    }
    assert by_profile["aggressive"]["occurrence_metrics"]["counts"] == {
        "tp": 240,
        "fp": 0,
        "fn": 0,
    }
    assert _all_keys(report).isdisjoint(
        {"case_results", "case_id", "text", "canonical_term", "slice_metrics"}
    )
