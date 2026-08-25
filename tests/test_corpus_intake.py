"""Contract tests for license-pinned PF-005 corpus intake."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.corpus_intake import (
    DEFAULT_SOURCE_SPEC_PATH,
    INTAKE_REPORT_SCHEMA_PATH,
    SOURCE_SPEC_SCHEMA_PATH,
    CorpusIntakeError,
    build_review_intake,
    main,
)
from evaluation.corpus_validator import validate_corpus_paths

_CHECKED_REPORT_PATH = Path("evaluation/results/curse-review-intake-v1.report.json")
_CHECKED_MANIFEST_PATH = Path("evaluation/splits/corpus-splits.v2.json")
_BUNDLED_LICENSE_PATH = Path("evaluation/sources/licenses/curse-detection-data-MIT.txt")
_ADDITIONAL_SOURCE_SPECS = {
    Path("evaluation/sources/kote.v1.json"): {
        "source_id": "kote",
        "revision": "cafd2c3f54a6f4b25ac74eaa02a2e76c3ef8c977",
        "artifact_sha256": "62c18dc385f7c140624b693a2806e98060daaf9e7427ceb7d050828d0a55f992",
        "license_spdx": "MIT",
        "target_count": 750,
    },
    Path("evaluation/sources/beep-korean-hate-speech.v1.json"): {
        "source_id": "beep-korean-hate-speech",
        "revision": "f8d05dce2b22007bb149e5139c0060c68ad8f94b",
        "artifact_sha256": "ebebacdcd023af2c4acc8c0a37695fb6433ac04fc009feff8f222724e303a5a9",
        "license_spdx": "CC-BY-SA-4.0",
        "target_count": None,
    },
}
_ADDITIONAL_REPORTS = {
    Path("evaluation/results/kote-review-intake-v1.report.json"): {
        "source_row_count": 40000,
        "selected_source_label_counts": {"__all__": 750},
        "sensitive_pattern_excluded_count": 45,
    },
    Path("evaluation/results/beep-review-intake-v1.report.json"): {
        "source_row_count": 7896,
        "selected_source_label_counts": {"hate": 250, "none": 250, "offensive": 250},
        "sensitive_pattern_excluded_count": 9,
    },
}
_BUFFER_SOURCE_SPECS = {
    Path("evaluation/sources/curse-detection-data.buffer-v1.json"): {
        "base_path": Path("evaluation/sources/curse-detection-data.v1.json"),
        "corpus_id": "koguard-curse-buffer-source-v1",
        "target_count": None,
        "target_by_source_label": {"0": 800, "1": 2000},
    },
    Path("evaluation/sources/kote.buffer-v1.json"): {
        "base_path": Path("evaluation/sources/kote.v1.json"),
        "corpus_id": "koguard-kote-buffer-source-v1",
        "target_count": 1050,
        "target_by_source_label": None,
    },
    Path("evaluation/sources/beep-korean-hate-speech.buffer-v1.json"): {
        "base_path": Path("evaluation/sources/beep-korean-hate-speech.v1.json"),
        "corpus_id": "koguard-beep-buffer-source-v1",
        "target_count": None,
        "target_by_source_label": {"hate": 250, "none": 550, "offensive": 250},
    },
}
_BUFFER_REPORTS = {
    Path("evaluation/results/curse-buffer-source-v1.report.json"): {
        "selected_count": 2800,
        "selected_source_label_counts": {"0": 800, "1": 2000},
    },
    Path("evaluation/results/kote-buffer-source-v1.report.json"): {
        "selected_count": 1050,
        "selected_source_label_counts": {"__all__": 1050},
    },
    Path("evaluation/results/beep-buffer-source-v1.report.json"): {
        "selected_count": 1050,
        "selected_source_label_counts": {"hate": 250, "none": 550, "offensive": 250},
    },
}


def _canonical_lf_sha256(content: bytes) -> str:
    return hashlib.sha256(content.replace(b"\r\n", b"\n")).hexdigest()


def test_intake_schemas_are_versioned_and_closed() -> None:
    source_schema = json.loads(SOURCE_SPEC_SCHEMA_PATH.read_text(encoding="utf-8"))
    report_schema = json.loads(INTAKE_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert source_schema["properties"]["schema_version"]["const"] == 2
    assert source_schema["additionalProperties"] is False
    assert source_schema["$defs"]["artifact"]["additionalProperties"] is False
    assert report_schema["properties"]["schema_version"]["const"] == 2
    assert report_schema["additionalProperties"] is False


def test_checked_source_spec_pins_license_revision_and_artifact() -> None:
    spec = json.loads(DEFAULT_SOURCE_SPEC_PATH.read_text(encoding="utf-8"))

    assert spec["source_id"] == "curse-detection-data"
    assert spec["source_name"] == "2runo/Curse-detection-data"
    assert spec["revision"] == "ff241621e103b6f220d30de324d0d07987887308"
    assert spec["artifact"]["sha256"] == (
        "1c3489417e4972dbbbdde19cc47bb8638292891f7f1a443ecbdc2e3c6843545a"
    )
    assert spec["artifact"]["line_count"] == 5825
    assert spec["license"]["spdx"] == "MIT"
    assert spec["license"]["redistribution_allowed"] is True
    assert spec["license"]["sha256"] == (
        "5cb5b18cc855e245f8e299b931a1203479a56fd79a752b102d623056ba5d7c2c"
    )
    assert (
        hashlib.sha256(_BUNDLED_LICENSE_PATH.read_bytes()).hexdigest() == spec["license"]["sha256"]
    )
    assert spec["intake"]["target_by_source_label"] == {"0": 500, "1": 2000}


@pytest.mark.parametrize(("source_path", "expected"), _ADDITIONAL_SOURCE_SPECS.items())
def test_additional_pf005_source_specs_are_pinned_and_review_only(
    source_path: Path,
    expected: dict[str, Any],
) -> None:
    spec = json.loads(source_path.read_text(encoding="utf-8"))

    assert spec["schema_version"] == 2
    assert spec["source_id"] == expected["source_id"]
    assert spec["revision"] == expected["revision"]
    assert spec["artifact"]["sha256"] == expected["artifact_sha256"]
    assert spec["license"]["spdx"] == expected["license_spdx"]
    assert spec["license"]["redistribution_allowed"] is True
    assert spec["intake"]["split"] == "tuning"
    assert spec["intake"]["target_count"] == expected["target_count"]


@pytest.mark.parametrize(("report_path", "expected"), _ADDITIONAL_REPORTS.items())
def test_additional_pf005_intake_reports_are_non_sensitive_and_pending_review(
    report_path: Path,
    expected: dict[str, Any],
) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["schema_version"] == 2
    assert report["source_row_count"] == expected["source_row_count"]
    assert report["selected_count"] == 750
    assert report["selected_source_label_counts"] == expected["selected_source_label_counts"]
    assert (
        report["sensitive_pattern_excluded_count"] == expected["sensitive_pattern_excluded_count"]
    )
    assert report["duplicate_text_excluded_count"] == 0
    assert report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": 750,
    }
    assert report["adjudication_quality"]["pending_review"] == 750
    assert report["gold_ready"] is False


@pytest.mark.parametrize(("source_path", "expected"), _BUFFER_SOURCE_SPECS.items())
def test_buffer_source_specs_extend_pinned_intakes_without_changing_rights(
    source_path: Path,
    expected: dict[str, Any],
) -> None:
    spec = json.loads(source_path.read_text(encoding="utf-8"))
    base = json.loads(expected["base_path"].read_text(encoding="utf-8"))

    assert spec["schema_version"] == 2
    for field in (
        "source_id",
        "source_name",
        "repository",
        "revision",
        "artifact",
        "license",
        "format",
    ):
        assert spec[field] == base[field]
    assert spec["intake"]["corpus_id"] == expected["corpus_id"]
    assert spec["intake"]["target_count"] == expected["target_count"]
    assert spec["intake"]["target_by_source_label"] == expected["target_by_source_label"]
    assert spec["license"]["redistribution_allowed"] is True


@pytest.mark.parametrize(("report_path", "expected"), _BUFFER_REPORTS.items())
def test_buffer_source_reports_are_aggregate_review_only(
    report_path: Path,
    expected: dict[str, Any],
) -> None:
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["selected_count"] == expected["selected_count"]
    assert report["selected_source_label_counts"] == expected["selected_source_label_counts"]
    assert report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": expected["selected_count"],
    }
    assert report["gold_ready"] is False
    serialized = json.dumps(report, ensure_ascii=False)
    for forbidden in ("case_id", "text", "canonical_term", "reviewer_id"):
        assert f'"{forbidden}"' not in serialized


def test_generic_tsv_intake_supports_headers_and_non_mit_sources(tmp_path: Path) -> None:
    artifact = tmp_path / "source.tsv"
    artifact.write_text(
        "comment\tclass\n첫 문장\tnone\n둘째 문장\toffensive\n셋째 문장\thate\n",
        encoding="utf-8",
    )
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 0})
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["source_id"] = "generic-tsv-source"
    spec["source_name"] = "example/generic-tsv"
    spec["license"]["spdx"] = "CC-BY-SA-4.0"
    spec["format"] = {
        "kind": "delimited",
        "delimiter": "\t",
        "encoding": "utf-8",
        "header_rows": 1,
        "text_column": 0,
        "label_column": 1,
        "allowed_labels": ["none", "offensive", "hate"],
    }
    spec["intake"] = {
        "corpus_id": "generic-tsv-review-intake",
        "split": "tuning",
        "selection": "stable-sha256-rank-v1",
        "target_count": 2,
        "target_by_source_label": None,
    }
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    result = build_review_intake(spec_path, artifact)

    assert result.report["source_row_count"] == 3
    assert result.report["source_label_counts"] == {"hate": 1, "none": 1, "offensive": 1}
    assert result.report["selected_count"] == 2
    assert sum(result.report["selected_source_label_counts"].values()) == 2
    assert all(case["source"]["name"] == "example/generic-tsv" for case in result.corpus["cases"])
    assert all(case["license"] == "CC-BY-SA-4.0" for case in result.corpus["cases"])


def test_unlabelled_source_and_duplicate_texts_are_supported_safely(tmp_path: Path) -> None:
    artifact = tmp_path / "source.tsv"
    artifact.write_text(
        "1\t중복 문장\tlabels-a\n2\t중복 문장\tlabels-b\n3\t고유 문장\tlabels-c\n",
        encoding="utf-8",
    )
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 0})
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["source_id"] = "unlabelled-tsv-source"
    spec["source_name"] = "example/unlabelled-tsv"
    spec["format"] = {
        "kind": "delimited",
        "delimiter": "\t",
        "encoding": "utf-8",
        "header_rows": 0,
        "text_column": 1,
        "label_column": None,
        "allowed_labels": None,
    }
    spec["intake"] = {
        "corpus_id": "unlabelled-tsv-review-intake",
        "split": "tuning",
        "selection": "stable-sha256-rank-v1",
        "target_count": 2,
        "target_by_source_label": None,
    }
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    result = build_review_intake(spec_path, artifact)

    assert result.report["source_row_count"] == 3
    assert result.report["duplicate_text_excluded_count"] == 1
    assert result.report["eligible_source_label_counts"] == {"__all__": 2}
    assert result.report["selected_source_label_counts"] == {"__all__": 2}
    assert len({case["text"] for case in result.corpus["cases"]}) == 2


def test_intake_is_deterministic_review_only_and_validator_compatible(tmp_path: Path) -> None:
    artifact = tmp_path / "source.txt"
    artifact.write_text(
        "첫 문장|0\n둘째 문장|0\n셋째 문장|0\n넷째 문장|1\n다섯째 문장|1\n", encoding="utf-8"
    )
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 2, "1": 1})
    corpus_path = tmp_path / "review-intake.json"
    report_path = tmp_path / "review-intake.report.json"

    first = build_review_intake(
        spec_path,
        artifact,
        output_path=corpus_path,
        report_path=report_path,
    )
    second = build_review_intake(spec_path, artifact)

    assert first.corpus == second.corpus
    assert first.report == second.report
    assert first.report["source_row_count"] == 5
    assert first.report["duplicate_text_excluded_count"] == 0
    assert first.report["sensitive_pattern_excluded_count"] == 0
    assert first.report["eligible_source_label_counts"] == {"0": 3, "1": 2}
    assert first.report["selected_count"] == 3
    assert first.report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": 3,
    }
    assert first.report["gold_ready"] is False
    assert first.report["source_statistics"] == [
        {"source_id": "unit-intake-source", "selected_count": 3, "share": 1.0}
    ]
    assert first.report["slice_counts"] == {"unadjudicated-intake": 3}
    assert first.report["adjudication_quality"]["pending_review"] == 3
    assert first.report["adjudication_quality"]["adjudicated"] == 0
    assert all(case["label"] == "review" for case in first.corpus["cases"])
    assert all(case["expected_matches"] == [] for case in first.corpus["cases"])
    assert all(case["slices"] == ["unadjudicated-intake"] for case in first.corpus["cases"])
    assert all("source label" not in case["notes"] for case in first.corpus["cases"])
    assert len({case["id"] for case in first.corpus["cases"]}) == 3
    assert validate_corpus_paths([corpus_path]).review_case_count == 3


def test_artifact_hash_mismatch_fails_without_source_text(tmp_path: Path) -> None:
    secret_text = "오류에 노출되면 안 되는 원문"
    artifact = tmp_path / "source.txt"
    artifact.write_text(f"{secret_text}|0\n", encoding="utf-8")
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 0})
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["artifact"]["sha256"] = "0" * 64
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CorpusIntakeError, match="artifact SHA-256 mismatch") as captured:
        build_review_intake(spec_path, artifact)

    assert secret_text not in str(captured.value)


def test_sensitive_patterns_are_excluded_before_selection(tmp_path: Path) -> None:
    artifact = tmp_path / "source.txt"
    artifact.write_text(
        "https://example.invalid/user/123456|0\n안전한 첫 문장|0\n안전한 둘째 문장|1\n",
        encoding="utf-8",
    )
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 1})

    result = build_review_intake(spec_path, artifact)

    assert result.report["sensitive_pattern_excluded_count"] == 1
    assert result.report["eligible_source_label_counts"] == {"0": 1, "1": 1}
    assert all("example.invalid" not in case["text"] for case in result.corpus["cases"])


def test_intake_rejects_unavailable_source_label_quota(tmp_path: Path) -> None:
    artifact = tmp_path / "source.txt"
    artifact.write_text("첫 문장|0\n둘째 문장|1\n", encoding="utf-8")
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 2, "1": 1})

    with pytest.raises(CorpusIntakeError, match="source label '0' has 1 rows; 2 required"):
        build_review_intake(spec_path, artifact)


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        (lambda spec: spec["artifact"].pop("sha256"), "artifact configuration is invalid"),
        (
            lambda spec: spec["intake"].update(corpus_id="Not Stable"),
            "intake corpus_id is invalid",
        ),
    ],
)
def test_malformed_nested_source_spec_is_rejected_as_contract_error(
    tmp_path: Path,
    mutation: Any,
    expected_message: str,
) -> None:
    artifact = tmp_path / "source.txt"
    artifact.write_text("첫 문장|0\n", encoding="utf-8")
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 0})
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    mutation(spec)
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(CorpusIntakeError, match=expected_message):
        build_review_intake(spec_path, artifact)


def test_report_omits_corpus_text_and_records_completion_blockers(tmp_path: Path) -> None:
    secret_text = "보고서에 없어야 하는 원문"
    artifact = tmp_path / "source.txt"
    artifact.write_text(f"{secret_text}|0\n다른 문장|1\n", encoding="utf-8")
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 1})

    result = build_review_intake(spec_path, artifact)
    serialized_report = json.dumps(result.report, ensure_ascii=False)

    assert secret_text not in serialized_report
    assert result.report["gold_ready"] is False
    assert result.report["completion_blockers"] == [
        "2 review cases still require Koguard-policy adjudication and exact spans.",
        "Automated sensitive-pattern exclusion still requires manual privacy review.",
        "Independent hidden evaluation material is not part of this public intake.",
    ]


def test_cli_writes_intake_and_reports_only_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    artifact = tmp_path / "source.txt"
    artifact.write_text("첫 문장|0\n둘째 문장|1\n", encoding="utf-8")
    spec_path = _write_spec(tmp_path, artifact, targets={"0": 1, "1": 1})
    output_path = tmp_path / "intake.json"
    report_path = tmp_path / "report.json"

    exit_code = main(
        [
            str(spec_path),
            str(artifact),
            "--output",
            str(output_path),
            "--report",
            str(report_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "rows=2" in captured.out
    assert "selected=2" in captured.out
    assert "gold_ready=false" in captured.out
    assert "첫 문장" not in captured.out
    assert captured.err == ""
    assert output_path.is_file()
    assert report_path.is_file()


def test_checked_review_intake_matches_pinned_contract() -> None:
    report_bytes = _CHECKED_REPORT_PATH.read_bytes()
    manifest_bytes = _CHECKED_MANIFEST_PATH.read_bytes()
    report = json.loads(report_bytes)
    manifest = json.loads(manifest_bytes)

    assert _canonical_lf_sha256(report_bytes) == (
        "54319c0e838ae2f61a7ed601ceefb951ebc84300888ed746c81ac8672020603f"
    )
    assert _canonical_lf_sha256(manifest_bytes) == (
        "06dc923ece416dee03cf6db984b319daa6290b7a1b3e212f2f8c0cbb042f846d"
    )
    assert report["selected_source_label_counts"] == {"0": 500, "1": 2000}
    assert report["duplicate_text_excluded_count"] == 0
    assert report["sensitive_pattern_excluded_count"] == 25
    assert report["eligible_source_label_counts"] == {"0": 3762, "1": 2038}
    assert report["generated_label_counts"]["review"] == 2500
    assert report["source_statistics"][0]["share"] == 1.0
    assert report["slice_counts"] == {"unadjudicated-intake": 2500}
    assert report["adjudication_quality"]["pending_review"] == 2500
    assert report["gold_ready"] is False
    assert manifest["manifest_version"] == 2
    assert len(manifest["assignments"]) == 2520


def test_canonical_lf_hash_is_checkout_independent() -> None:
    assert _canonical_lf_sha256(b'{"value": 1}\r\n') == _canonical_lf_sha256(b'{"value": 1}\n')


def _write_spec(
    tmp_path: Path,
    artifact: Path,
    *,
    targets: dict[str, int],
) -> Path:
    spec = copy.deepcopy(json.loads(DEFAULT_SOURCE_SPEC_PATH.read_text(encoding="utf-8")))
    content = artifact.read_bytes()
    spec["source_id"] = "unit-intake-source"
    spec["revision"] = "unit-revision"
    spec["artifact"]["url"] = "https://example.invalid/unit-source.txt"
    spec["artifact"]["sha256"] = hashlib.sha256(content).hexdigest()
    spec["artifact"]["size_bytes"] = len(content)
    spec["artifact"]["line_count"] = len(content.decode("utf-8").splitlines())
    spec["intake"]["corpus_id"] = "unit-review-intake"
    spec["intake"]["target_by_source_label"] = targets
    return _write_json(tmp_path / "source-spec.json", spec)


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
