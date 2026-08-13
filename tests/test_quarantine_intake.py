"""Contract tests for rights-pending quarantine corpus intake."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.corpus_validator import validate_corpus_paths
from evaluation.quarantine_intake import (
    QUARANTINE_REPORT_SCHEMA_PATH,
    QUARANTINE_SOURCE_SCHEMA_PATH,
    QuarantineIntakeError,
    build_quarantine_intake,
    main,
)

_CHECKED_SOURCE_PATH = Path("evaluation/sources/candidates/zizun-korean-malicious-comments.v1.json")
_DECLARED_LICENSE_PATH = Path("evaluation/sources/licenses/zizun-declared-MIT.txt")
_CHECKED_REPORT_PATH = Path("evaluation/results/zizun-quarantine-intake-v1.report.json")


def test_quarantine_schemas_are_versioned_and_closed() -> None:
    source_schema = json.loads(QUARANTINE_SOURCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    report_schema = json.loads(QUARANTINE_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert source_schema["properties"]["schema_version"]["const"] == 1
    assert source_schema["additionalProperties"] is False
    assert source_schema["$defs"]["artifact"]["additionalProperties"] is False
    assert source_schema["$defs"]["rightsReview"]["properties"]["status"]["const"] == "pending"
    assert report_schema["properties"]["schema_version"]["const"] == 1
    assert report_schema["additionalProperties"] is False
    assert report_schema["properties"]["gold_ready"]["const"] is False


def test_checked_zizun_source_is_pinned_and_quarantined() -> None:
    spec = json.loads(_CHECKED_SOURCE_PATH.read_text(encoding="utf-8"))

    assert spec["revision"] == "50b92f50e89bb594db5c9ecafea8d48c1dd5b943"
    assert spec["artifacts"]["dataset"]["sha256"] == (
        "8fee1801737cd9d1d3bd38eab7ba6b9ba1d8b91b566f49d980c112dcf778be04"
    )
    assert spec["artifacts"]["dataset"]["row_count"] == 10000
    assert spec["artifacts"]["license"]["sha256"] == (
        "719828109791321378c5b4b479c927f6e971530b5ce5088ff361b7ccf3e3d38d"
    )
    assert (
        hashlib.sha256(_DECLARED_LICENSE_PATH.read_bytes()).hexdigest()
        == (spec["artifacts"]["license"]["sha256"])
    )
    assert spec["rights_review"]["status"] == "pending"
    assert spec["rights_review"]["redistribution_allowed"] is False
    assert spec["rights_review"]["allowed_scope"] == "local-quarantine-analysis-only"
    component_licenses = {
        component["source_id"]: component["declared_license"] for component in spec["components"]
    }
    assert component_licenses["korean-hate-speech"] == "CC-BY-SA-4.0"
    assert component_licenses["curse-detection-data"] == "MIT"


def test_checked_zizun_report_records_overlap_without_raw_text() -> None:
    report = json.loads(_CHECKED_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["source_row_count"] == 10000
    assert report["source_label_counts"] == {"0": 4983, "1": 4992, "missing": 25}
    assert report["direct_overlap_excluded"] == 1402
    assert report["normalized_overlap_excluded"] == 2010
    assert report["selected_source_label_counts"] == {"0": 250, "1": 250}
    assert report["rights_review_status"] == "pending"
    assert report["redistribution_allowed"] is False
    assert report["independent_source_ready"] is False
    assert report["gold_ready"] is False
    assert '"text"' not in json.dumps(report, ensure_ascii=False)


def test_quarantine_intake_filters_overlap_privacy_and_malformed_rows(tmp_path: Path) -> None:
    dataset_path = tmp_path / "dataset.tsv"
    dataset_path.write_text(
        "content\tlable\n"
        "정상 첫째\t0\n"
        "정상 둘째\t0\n"
        "욕설 후보\t1\n"
        "다른 후보\t1\n"
        "겹친 문장\t1\n"
        "중 복\t0\n"
        "중복\t0\n"
        "https://example.invalid\t0\n"
        "라벨 없음\n",
        encoding="utf-8",
    )
    license_path = _write_text(tmp_path / "LICENSE", "Declared license\n")
    provenance_path = _write_text(tmp_path / "README.md", "Composite source statement\n")
    exclusion_path = _write_text(tmp_path / "excluded.txt", "겹친 문장|1\n")
    spec_path = _write_spec(
        tmp_path,
        dataset_path,
        license_path,
        provenance_path,
        exclusion_path,
        targets={"0": 1, "1": 1},
    )
    output_path = tmp_path / "quarantine.json"
    report_path = tmp_path / "report.json"

    result = build_quarantine_intake(
        spec_path,
        dataset_path,
        license_path,
        provenance_path,
        [exclusion_path],
        output_path=output_path,
        report_path=report_path,
    )

    assert result.report["source_row_count"] == 9
    assert result.report["source_label_counts"] == {"0": 5, "1": 3, "missing": 1}
    assert result.report["direct_overlap_excluded"] == 1
    assert result.report["normalized_overlap_excluded"] == 1
    assert result.report["sensitive_pattern_excluded"] == 1
    assert result.report["normalized_duplicate_excluded"] == 1
    assert result.report["eligible_source_label_counts"] == {"0": 3, "1": 2}
    assert result.report["selected_source_label_counts"] == {"0": 1, "1": 1}
    assert result.report["generated_label_counts"] == {
        "positive": 0,
        "hard-negative": 0,
        "review": 2,
    }
    assert result.report["rights_review_status"] == "pending"
    assert result.report["redistribution_allowed"] is False
    assert result.report["independent_source_ready"] is False
    assert result.report["gold_ready"] is False
    assert all(case["label"] == "review" for case in result.corpus["cases"])
    assert all(case["expected_matches"] == [] for case in result.corpus["cases"])
    assert all(case["slices"] == ["unadjudicated-intake"] for case in result.corpus["cases"])
    assert all(case["source"]["redistribution_allowed"] is False for case in result.corpus["cases"])
    assert all(case["license"] == "LicenseRef-PendingReview" for case in result.corpus["cases"])
    serialized_corpus = json.dumps(result.corpus, ensure_ascii=False)
    assert '"source_label"' not in serialized_corpus
    assert "겹친 문장" not in serialized_corpus
    assert '"text": "https://example.invalid"' not in serialized_corpus
    assert validate_corpus_paths([output_path]).review_case_count == 2
    assert report_path.is_file()


def test_quarantine_intake_is_deterministic_and_report_omits_text(tmp_path: Path) -> None:
    dataset_path = _write_text(
        tmp_path / "dataset.tsv",
        "content\tlable\n비공개 후보 하나\t0\n비공개 후보 둘\t1\n",
    )
    license_path = _write_text(tmp_path / "LICENSE", "Declared license\n")
    provenance_path = _write_text(tmp_path / "README.md", "Composite source statement\n")
    exclusion_path = _write_text(tmp_path / "excluded.txt", "다른 문장|0\n")
    spec_path = _write_spec(
        tmp_path,
        dataset_path,
        license_path,
        provenance_path,
        exclusion_path,
        targets={"0": 1, "1": 1},
    )

    first = build_quarantine_intake(
        spec_path, dataset_path, license_path, provenance_path, [exclusion_path]
    )
    second = build_quarantine_intake(
        spec_path, dataset_path, license_path, provenance_path, [exclusion_path]
    )

    assert first == second
    serialized_report = json.dumps(first.report, ensure_ascii=False)
    assert "비공개 후보" not in serialized_report
    assert "canonical_term" not in serialized_report


def test_quarantine_intake_rejects_hash_mismatch_without_echoing_text(tmp_path: Path) -> None:
    secret_text = "오류에 노출되면 안 되는 후보"
    dataset_path = _write_text(tmp_path / "dataset.tsv", f"content\tlable\n{secret_text}\t0\n")
    license_path = _write_text(tmp_path / "LICENSE", "Declared license\n")
    provenance_path = _write_text(tmp_path / "README.md", "Composite source statement\n")
    exclusion_path = _write_text(tmp_path / "excluded.txt", "다른 문장|0\n")
    spec_path = _write_spec(
        tmp_path,
        dataset_path,
        license_path,
        provenance_path,
        exclusion_path,
        targets={"0": 1, "1": 0},
    )
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["artifacts"]["dataset"]["sha256"] = "0" * 64
    spec_path.write_text(json.dumps(spec, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(QuarantineIntakeError, match="dataset SHA-256 mismatch") as captured:
        build_quarantine_intake(
            spec_path,
            dataset_path,
            license_path,
            provenance_path,
            [exclusion_path],
        )

    assert secret_text not in str(captured.value)


def test_quarantine_cli_prints_only_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_text = "CLI에 노출되면 안 되는 후보"
    dataset_path = _write_text(
        tmp_path / "dataset.tsv",
        f"content\tlable\n{secret_text}\t0\n다른 후보\t1\n",
    )
    license_path = _write_text(tmp_path / "LICENSE", "Declared license\n")
    provenance_path = _write_text(tmp_path / "README.md", "Composite source statement\n")
    exclusion_path = _write_text(tmp_path / "excluded.txt", "다른 문장|0\n")
    spec_path = _write_spec(
        tmp_path,
        dataset_path,
        license_path,
        provenance_path,
        exclusion_path,
        targets={"0": 1, "1": 1},
    )

    exit_code = main(
        [
            str(spec_path),
            str(dataset_path),
            str(license_path),
            str(provenance_path),
            "--exclusion",
            str(exclusion_path),
            "--output",
            str(tmp_path / "output.json"),
            "--report",
            str(tmp_path / "report.json"),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "rows=2" in captured.out
    assert "selected=2" in captured.out
    assert "rights=pending" in captured.out
    assert secret_text not in captured.out
    assert captured.err == ""


def _write_spec(
    tmp_path: Path,
    dataset_path: Path,
    license_path: Path,
    provenance_path: Path,
    exclusion_path: Path,
    *,
    targets: dict[str, int],
) -> Path:
    spec: dict[str, Any] = {
        "schema_version": 1,
        "source_id": "unit-quarantine-source",
        "repository": "https://example.invalid/source",
        "revision": "fixed-revision",
        "artifacts": {
            "dataset": _artifact(dataset_path, row_count=_data_row_count(dataset_path)),
            "license": _artifact(license_path),
            "provenance": _artifact(provenance_path),
        },
        "format": {
            "kind": "tsv-header",
            "text_column": "content",
            "label_column": "lable",
            "allowed_labels": ["0", "1"],
        },
        "components": [
            {
                "source_id": "component-a",
                "reference": "https://example.invalid/component-a",
                "declared_license": "CC-BY-SA-4.0",
                "stated_row_count": 1,
            }
        ],
        "rights_review": {
            "status": "pending",
            "redistribution_allowed": False,
            "allowed_scope": "local-quarantine-analysis-only",
            "blockers": ["Composite source rights require review."],
        },
        "exclusions": [
            {
                "source_id": "existing-source",
                "artifact_sha256": hashlib.sha256(exclusion_path.read_bytes()).hexdigest(),
                "format": "pipe-last-label",
            }
        ],
        "intake": {
            "corpus_id": "unit-quarantine-intake",
            "split": "tuning",
            "selection": "stable-sha256-rank-v1",
            "target_by_source_label": targets,
        },
    }
    return _write_json(tmp_path / "source-spec.json", spec)


def _artifact(path: Path, *, row_count: int | None = None) -> dict[str, Any]:
    artifact: dict[str, Any] = {
        "url": f"https://example.invalid/{path.name}",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "size_bytes": len(path.read_bytes()),
    }
    if row_count is not None:
        artifact["row_count"] = row_count
    return artifact


def _data_row_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) - 1


def _write_text(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
