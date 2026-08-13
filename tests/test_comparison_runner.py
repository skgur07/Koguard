"""Contract tests for the reproducible Koguard/Korcen comparison runner."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from evaluation.comparison_runner import (
    COMPARISON_REPORT_SCHEMA_PATH,
    KORCEN_PROFILE,
    KORCEN_VERSION,
    ComparisonError,
    DetectorCapabilities,
    DetectorRun,
    DetectorSpec,
    Prediction,
    PredictionMatch,
    RuntimeMetadata,
    make_koguard_spec,
    make_korcen_spec,
    run_comparison,
)

_CORPUS_PATH = (
    Path(__file__).parent / "fixtures" / "corpus_validation" / "valid" / "public-regression.json"
)
_GENERATED_AT = datetime(2026, 8, 12, tzinfo=UTC)


def test_report_schema_declares_versioned_closed_contract() -> None:
    schema = json.loads(COMPARISON_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {
        "schema_version",
        "generated_at",
        "corpus",
        "runner",
        "detectors",
        "case_results",
    }
    assert schema["$defs"]["detectorReport"]["additionalProperties"] is False


def test_comparison_records_artifacts_metrics_slices_and_unsupported_occurrences(
    tmp_path: Path,
) -> None:
    specs = _make_specs(tmp_path)

    report = run_comparison(
        [_CORPUS_PATH],
        specs,
        worker_runner=_fake_worker,
        generated_at=_GENERATED_AT,
    ).to_dict()

    assert report["schema_version"] == 1
    assert report["generated_at"] == "2026-08-12T00:00:00+00:00"
    assert report["corpus"]["case_count"] == 3
    assert report["corpus"]["evaluated_case_count"] == 2
    assert report["corpus"]["excluded_review_count"] == 1
    assert len(report["corpus"]["sha256"]) == 64

    koguard = _detector_report(report, "koguard")
    assert koguard["artifact"]["package"] == "koguard"
    assert koguard["artifact"]["version"] == "0.1.0"
    assert koguard["artifact"]["sha256"] == sha256(specs[0].artifact_path.read_bytes()).hexdigest()
    assert koguard["settings"] == {"all_matchers_enabled": True}
    assert koguard["sentence_metrics"]["counts"] == {"tp": 2, "fp": 0, "fn": 0, "tn": 0}
    assert koguard["sentence_metrics"]["precision"] == 1.0
    assert koguard["occurrence_metrics"]["status"] == "available"
    assert koguard["occurrence_metrics"]["exact"]["counts"] == {"tp": 2, "fp": 0, "fn": 0}
    assert koguard["occurrence_metrics"]["span"]["counts"] == {"tp": 2, "fp": 0, "fn": 0}
    assert koguard["occurrence_metrics"]["canonical"]["counts"] == {
        "tp": 2,
        "fp": 0,
        "fn": 0,
    }

    korcen = _detector_report(report, "korcen")
    assert korcen["artifact"]["version"] == KORCEN_VERSION
    assert korcen["profile"] == KORCEN_PROFILE
    assert korcen["settings"] == {"foreign": False}
    assert korcen["sentence_metrics"]["counts"] == {"tp": 1, "fp": 0, "fn": 1, "tn": 0}
    assert korcen["occurrence_metrics"] == {
        "status": "unsupported",
        "reason": "detector does not expose occurrence spans or canonical terms",
    }

    direct_slice = _slice_report(koguard, "direct")
    assert direct_slice["case_count"] == 1
    assert direct_slice["sentence_metrics"]["counts"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 0}
    benign_slice = _slice_report(korcen, "benign-substring")
    assert benign_slice["sentence_metrics"]["counts"] == {"tp": 1, "fp": 0, "fn": 0, "tn": 0}


def test_report_does_not_include_corpus_text_or_expected_terms(tmp_path: Path) -> None:
    report = run_comparison(
        [_CORPUS_PATH],
        _make_specs(tmp_path),
        worker_runner=_fake_worker,
        generated_at=_GENERATED_AT,
    ).to_dict()

    serialized = json.dumps(report, ensure_ascii=False)
    assert "금칙어라고 썼다" not in serialized
    assert "시발점은 시작 위치다" not in serialized
    assert "금칙어" not in serialized
    assert {case["case_id"] for case in report["case_results"]} == {
        "example-positive-direct",
        "example-positive-substring",
    }


def test_detector_predictions_cannot_overwrite_gold_annotations(tmp_path: Path) -> None:
    report = run_comparison(
        [_CORPUS_PATH],
        _make_specs(tmp_path),
        worker_runner=_fake_worker,
        generated_at=_GENERATED_AT,
    ).to_dict()

    positive = next(
        case for case in report["case_results"] if case["case_id"] == "example-positive-direct"
    )
    korcen = next(item for item in positive["detectors"] if item["detector_id"] == "korcen")

    assert positive["gold_detected"] is True
    assert positive["gold_occurrence_count"] == 1
    assert korcen["detected"] is False
    assert korcen["sentence_outcome"] == "fn"


def test_same_inputs_reproduce_semantic_report_and_fingerprint(tmp_path: Path) -> None:
    specs = _make_specs(tmp_path)

    first = run_comparison(
        [_CORPUS_PATH], specs, worker_runner=_fake_worker, generated_at=_GENERATED_AT
    ).to_dict()
    second = run_comparison(
        [_CORPUS_PATH], specs, worker_runner=_fake_worker, generated_at=_GENERATED_AT
    ).to_dict()

    assert first == second
    assert first["runner"]["configuration_sha256"] == second["runner"]["configuration_sha256"]


def test_pinned_korcen_spec_rejects_wrong_artifact_hash(tmp_path: Path) -> None:
    wrong_wheel = _write_wheel(tmp_path / "korcen-1.0.3-py3-none-any.whl", "korcen", "1.0.3")

    with pytest.raises(ComparisonError, match="Korcen artifact SHA-256 mismatch"):
        make_korcen_spec(wrong_wheel, Path("python"))


def test_koguard_spec_exposes_only_implemented_profile_path() -> None:
    with pytest.raises(ComparisonError, match="unsupported Koguard profile"):
        make_koguard_spec(
            Path("not-read-for-unsupported-profile.whl"),
            Path("python"),
            profile="future-default",
        )


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "unexpected"])
def test_worker_predictions_must_match_evaluated_case_ids(
    tmp_path: Path,
    mutation: str,
) -> None:
    specs = _make_specs(tmp_path)

    def invalid_worker(spec: DetectorSpec, case_inputs: Sequence[tuple[str, str]]) -> DetectorRun:
        valid = _fake_worker(spec, case_inputs)
        if mutation == "missing":
            predictions = valid.predictions[:-1]
        elif mutation == "duplicate":
            predictions = valid.predictions + (valid.predictions[0],)
        else:
            predictions = valid.predictions + (Prediction("unexpected-id", False, ()),)
        return replace(valid, predictions=predictions)

    with pytest.raises(ComparisonError, match="prediction case IDs"):
        run_comparison([_CORPUS_PATH], specs, worker_runner=invalid_worker)


def test_boolean_detector_rejects_occurrence_output(tmp_path: Path) -> None:
    specs = _make_specs(tmp_path)

    def invalid_worker(spec: DetectorSpec, case_inputs: Sequence[tuple[str, str]]) -> DetectorRun:
        valid = _fake_worker(spec, case_inputs)
        if spec.detector_id != "korcen":
            return valid
        predictions = tuple(
            replace(prediction, matches=(PredictionMatch(0, 1, "unexpected"),))
            for prediction in valid.predictions
        )
        return replace(valid, predictions=predictions)

    with pytest.raises(ComparisonError, match="does not support occurrence output"):
        run_comparison([_CORPUS_PATH], specs, worker_runner=invalid_worker)


def test_corpus_with_only_review_cases_is_rejected(tmp_path: Path) -> None:
    payload = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    payload["corpus_id"] = "review-only"
    payload["cases"] = [payload["cases"][2]]
    review_only = tmp_path / "review-only.json"
    review_only.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ComparisonError, match="no automatically evaluable cases"):
        run_comparison([review_only], _make_specs(tmp_path), worker_runner=_fake_worker)


def _make_specs(tmp_path: Path) -> tuple[DetectorSpec, DetectorSpec]:
    koguard_wheel = _write_wheel(tmp_path / "koguard-0.1.0-py3-none-any.whl", "koguard", "0.1.0")
    korcen_wheel = _write_wheel(
        tmp_path / "korcen-1.0.3-py3-none-any.whl", "korcen", KORCEN_VERSION
    )
    return (
        DetectorSpec(
            detector_id="koguard",
            package="koguard",
            expected_version="0.1.0",
            profile="current-all-enabled",
            artifact_path=koguard_wheel,
            python_executable=Path("python"),
            expected_sha256=None,
        ),
        DetectorSpec(
            detector_id="korcen",
            package="korcen",
            expected_version=KORCEN_VERSION,
            profile=KORCEN_PROFILE,
            artifact_path=korcen_wheel,
            python_executable=Path("python"),
            expected_sha256=sha256(korcen_wheel.read_bytes()).hexdigest(),
        ),
    )


def _fake_worker(
    spec: DetectorSpec,
    case_inputs: Sequence[tuple[str, str]],
) -> DetectorRun:
    case_ids = [case_id for case_id, _ in case_inputs]
    assert case_ids == ["example-positive-direct", "example-positive-substring"]
    runtime = RuntimeMetadata(
        python_version="3.11.9",
        implementation="CPython",
        platform="unit-test",
        dependencies=(),
        suppressed_output=False,
    )
    if spec.detector_id == "koguard":
        return DetectorRun(
            detector_id="koguard",
            package="koguard",
            version="0.1.0",
            profile="current-all-enabled",
            capabilities=DetectorCapabilities(
                sentence=True,
                occurrences=True,
                spans=True,
                canonical_terms=True,
            ),
            runtime=runtime,
            predictions=(
                Prediction(
                    "example-positive-direct",
                    True,
                    (PredictionMatch(0, 3, "금칙어"),),
                ),
                Prediction(
                    "example-positive-substring",
                    True,
                    (PredictionMatch(0, 2, "시발"),),
                ),
            ),
            settings=(("all_matchers_enabled", True),),
        )
    return DetectorRun(
        detector_id="korcen",
        package="korcen",
        version=KORCEN_VERSION,
        profile=KORCEN_PROFILE,
        capabilities=DetectorCapabilities(
            sentence=True,
            occurrences=False,
            spans=False,
            canonical_terms=False,
        ),
        runtime=runtime,
        predictions=(
            Prediction("example-positive-direct", False, None),
            Prediction("example-positive-substring", True, None),
        ),
        settings=(("foreign", False),),
    )


def _write_wheel(path: Path, package: str, version: str) -> Path:
    dist_info = f"{package.replace('-', '_')}-{version}.dist-info"
    with ZipFile(path, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{dist_info}/METADATA",
            f"Metadata-Version: 2.3\nName: {package}\nVersion: {version}\n",
        )
    return path


def _detector_report(report: dict[str, Any], detector_id: str) -> dict[str, Any]:
    return next(item for item in report["detectors"] if item["detector_id"] == detector_id)


def _slice_report(detector: dict[str, Any], slice_name: str) -> dict[str, Any]:
    return next(item for item in detector["slice_metrics"] if item["slice"] == slice_name)
