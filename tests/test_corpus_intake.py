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


def test_intake_schemas_are_versioned_and_closed() -> None:
    source_schema = json.loads(SOURCE_SPEC_SCHEMA_PATH.read_text(encoding="utf-8"))
    report_schema = json.loads(INTAKE_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert source_schema["properties"]["schema_version"]["const"] == 1
    assert source_schema["additionalProperties"] is False
    assert source_schema["$defs"]["artifact"]["additionalProperties"] is False
    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["additionalProperties"] is False


def test_checked_source_spec_pins_license_revision_and_artifact() -> None:
    spec = json.loads(DEFAULT_SOURCE_SPEC_PATH.read_text(encoding="utf-8"))

    assert spec["source_id"] == "curse-detection-data"
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

    assert hashlib.sha256(report_bytes).hexdigest() == (
        "385832a9b0d264eaa4c3bc248f64eec6287ff0451d7a1a431ae29dab2b1c7af9"
    )
    assert hashlib.sha256(manifest_bytes).hexdigest() == (
        "ae9b87258ebf02f8ef6078f290360ff1ab1b2ea9f5566842e4d7e319fe4fd502"
    )
    assert report["selected_source_label_counts"] == {"0": 500, "1": 2000}
    assert report["sensitive_pattern_excluded_count"] == 25
    assert report["eligible_source_label_counts"] == {"0": 3762, "1": 2038}
    assert report["generated_label_counts"]["review"] == 2500
    assert report["source_statistics"][0]["share"] == 1.0
    assert report["slice_counts"] == {"unadjudicated-intake": 2500}
    assert report["adjudication_quality"]["pending_review"] == 2500
    assert report["gold_ready"] is False
    assert manifest["manifest_version"] == 2
    assert len(manifest["assignments"]) == 2520


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
