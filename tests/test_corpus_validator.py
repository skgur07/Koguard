"""Contract tests for the service-evaluation corpus schema and validator."""

import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.corpus_validator import (
    CORPUS_SCHEMA_PATH,
    CorpusValidationError,
    main,
    validate_corpus_paths,
)

_FIXTURES = Path(__file__).parent / "fixtures" / "corpus_validation"
_VALID_CORPUS = _FIXTURES / "valid" / "public-regression.json"
_INVALID_FIXTURES = _FIXTURES / "invalid"


def test_schema_declares_closed_required_annotation_contract() -> None:
    schema = json.loads(CORPUS_SCHEMA_PATH.read_text(encoding="utf-8"))
    case_schema = schema["$defs"]["case"]
    match_schema = schema["$defs"]["expectedMatch"]

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert case_schema["additionalProperties"] is False
    assert set(case_schema["required"]) == {
        "id",
        "text",
        "label",
        "expected_matches",
        "slices",
        "source",
        "license",
        "split",
        "notes",
    }
    assert match_schema["additionalProperties"] is False
    assert set(match_schema["required"]) == {"start", "end", "canonical_term"}
    assert case_schema["properties"]["label"]["enum"] == [
        "positive",
        "hard-negative",
        "review",
    ]
    assert case_schema["properties"]["split"]["enum"] == [
        "regression",
        "tuning",
        "evaluation",
        "private",
    ]


def test_valid_public_regression_fixture_returns_summary() -> None:
    summary = validate_corpus_paths([_VALID_CORPUS])

    assert summary.file_count == 1
    assert summary.case_count == 3
    assert summary.review_case_count == 1
    assert summary.split_counts == (("regression", 3),)


@pytest.mark.parametrize(
    ("fixture_name", "expected_message"),
    [
        ("span-out-of-bounds.json", "end must not exceed text length"),
        ("duplicate-id.json", "duplicate case id"),
        ("missing-license.json", "missing required field: license"),
        ("unknown-slice.json", "unsupported slice"),
    ],
)
def test_invalid_fixtures_are_rejected(fixture_name: str, expected_message: str) -> None:
    with pytest.raises(CorpusValidationError, match=expected_message):
        validate_corpus_paths([_INVALID_FIXTURES / fixture_name])


@pytest.mark.parametrize(
    ("label", "expected_matches", "expected_message"),
    [
        ("positive", [], "positive case must contain at least one expected match"),
        (
            "hard-negative",
            [{"start": 0, "end": 1, "canonical_term": "금"}],
            "hard-negative case must not contain expected matches",
        ),
        ("unknown", [], "unsupported label"),
    ],
)
def test_case_label_controls_expected_match_contract(
    tmp_path: Path,
    label: str,
    expected_matches: list[dict[str, object]],
    expected_message: str,
) -> None:
    corpus = _valid_payload()
    corpus["cases"][0]["label"] = label
    corpus["cases"][0]["expected_matches"] = expected_matches
    corpus_path = _write_payload(tmp_path / "label.json", corpus)

    with pytest.raises(CorpusValidationError, match=expected_message):
        validate_corpus_paths([corpus_path])


def test_expected_matches_must_be_sorted_and_non_overlapping(tmp_path: Path) -> None:
    corpus = _valid_payload()
    corpus["cases"][0]["text"] = "금칙어 금칙어"
    corpus["cases"][0]["expected_matches"] = [
        {"start": 4, "end": 7, "canonical_term": "금칙어"},
        {"start": 0, "end": 3, "canonical_term": "금칙어"},
    ]
    corpus_path = _write_payload(tmp_path / "unsorted.json", corpus)

    with pytest.raises(CorpusValidationError, match="must be sorted by start and must not overlap"):
        validate_corpus_paths([corpus_path])


def test_duplicate_ids_are_rejected_across_files(tmp_path: Path) -> None:
    first = _write_payload(tmp_path / "first.json", _valid_payload())
    second = _write_payload(tmp_path / "second.json", _valid_payload())

    with pytest.raises(CorpusValidationError, match="duplicate case id"):
        validate_corpus_paths([first, second])


@pytest.mark.parametrize(
    ("split", "source_kind", "redistribution_allowed", "license_name", "expected_message"),
    [
        ("regression", "licensed", False, "MIT", "regression case must be redistributable"),
        ("private", "licensed", False, "MIT", "private split requires private source"),
        (
            "private",
            "private",
            False,
            "MIT",
            "private split must use LicenseRef-Private",
        ),
    ],
)
def test_split_enforces_distribution_boundary(
    tmp_path: Path,
    split: str,
    source_kind: str,
    redistribution_allowed: bool,
    license_name: str,
    expected_message: str,
) -> None:
    corpus = _valid_payload()
    case = corpus["cases"][0]
    case["split"] = split
    case["source"]["kind"] = source_kind
    case["source"]["redistribution_allowed"] = redistribution_allowed
    case["license"] = license_name
    corpus_path = _write_payload(tmp_path / "split.json", corpus)

    with pytest.raises(CorpusValidationError, match=expected_message):
        validate_corpus_paths([corpus_path])


@pytest.mark.parametrize("split", ["tuning", "evaluation"])
def test_licensed_nonpublic_split_accepts_pinned_nonredistributable_source(
    tmp_path: Path,
    split: str,
) -> None:
    corpus = _valid_payload()
    case = corpus["cases"][0]
    case["split"] = split
    case["source"] = {
        "kind": "licensed",
        "name": "Licensed evaluation fixture",
        "reference": "https://example.invalid/dataset",
        "revision": "fixed-revision",
        "redistribution_allowed": False,
    }
    corpus_path = _write_payload(tmp_path / f"{split}.json", corpus)

    summary = validate_corpus_paths([corpus_path])

    assert summary.split_counts == ((split, 1),)


def test_private_split_accepts_private_license_boundary(tmp_path: Path) -> None:
    corpus = _valid_payload()
    case = corpus["cases"][0]
    case["split"] = "private"
    case["source"] = {
        "kind": "private",
        "name": "Private service fixture",
        "reference": None,
        "revision": None,
        "redistribution_allowed": False,
    }
    case["license"] = "LicenseRef-Private"
    corpus_path = _write_payload(tmp_path / "private.json", corpus)

    summary = validate_corpus_paths([corpus_path])

    assert summary.split_counts == (("private", 1),)


def test_cli_reports_locations_without_echoing_corpus_text(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main([str(_INVALID_FIXTURES / "span-out-of-bounds.json")])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "cases[0].expected_matches[0].end" in captured.err
    assert "노출되면 안 되는 원문" not in captured.err
    assert captured.out == ""


def test_cli_accepts_directories_and_reports_review_count(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main([str(_FIXTURES / "valid")])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validated 3 cases in 1 file" in captured.out
    assert "review=1" in captured.out
    assert captured.err == ""


def _valid_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "corpus_id": "unit-corpus",
        "cases": [
            {
                "id": "unit-positive",
                "text": "금칙어",
                "label": "positive",
                "expected_matches": [{"start": 0, "end": 3, "canonical_term": "금칙어"}],
                "slices": ["direct"],
                "source": {
                    "kind": "curated",
                    "name": "Koguard unit fixture",
                    "reference": None,
                    "revision": None,
                    "redistribution_allowed": True,
                },
                "license": "MIT",
                "split": "regression",
                "notes": "Validator contract fixture.",
            }
        ],
    }


def _write_payload(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
