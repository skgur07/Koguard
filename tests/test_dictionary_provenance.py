"""Contract tests for packaged dictionary provenance and promotion validation."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
from evaluation.dictionary_provenance import (
    DEFAULT_ALIASES_PATH,
    DEFAULT_BADWORDS_PATH,
    DICTIONARY_PROVENANCE_PATH,
    DICTIONARY_PROVENANCE_SCHEMA_PATH,
    DictionaryProvenanceError,
    main,
    validate_dictionary_provenance,
)

from koguard.engine.normalizer import normalize_text


def test_schema_declares_closed_candidate_and_source_contracts() -> None:
    schema = json.loads(DICTIONARY_PROVENANCE_SCHEMA_PATH.read_text(encoding="utf-8"))
    candidate = schema["$defs"]["candidate"]
    source = schema["$defs"]["source"]

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert candidate["additionalProperties"] is False
    assert set(candidate["required"]) == {
        "candidate_id",
        "surface",
        "normalized_surface",
        "canonical",
        "normalized_canonical",
        "representation",
        "matcher",
        "target_layer",
        "classification",
        "status",
        "source_id",
        "evaluation_refs",
        "review",
        "notes",
    }
    assert candidate["properties"]["target_layer"]["enum"] == ["core", "ai-candidate"]
    assert candidate["properties"]["classification"]["enum"] == [
        "positive",
        "hard-negative",
        "review",
    ]
    assert source["additionalProperties"] is False
    assert set(source["required"]) == {
        "source_id",
        "kind",
        "name",
        "reference",
        "revision",
        "license",
        "license_status",
        "redistribution_allowed",
    }


def test_bundled_manifest_covers_every_packaged_literal_and_alias() -> None:
    summary = validate_dictionary_provenance(
        DICTIONARY_PROVENANCE_PATH,
        badwords_path=DEFAULT_BADWORDS_PATH,
        aliases_path=DEFAULT_ALIASES_PATH,
    )

    assert summary.source_count == 3
    assert summary.candidate_count == 73
    assert summary.packaged_literal_count == 65
    assert summary.packaged_alias_count == 5
    assert summary.ai_candidate_count == 0
    assert summary.pending_review_count == 0


def test_provenance_manifest_stays_out_of_runtime_dictionary_data() -> None:
    payload = json.loads(DICTIONARY_PROVENANCE_PATH.read_text(encoding="utf-8"))

    assert payload["manifest_id"] == "koguard-default-dictionary-v1"
    assert len(payload["candidates"]) == 73
    assert not files("koguard.data").joinpath("provenance.json").is_file()


def test_missing_packaged_literal_coverage_is_rejected_without_echoing_surface(
    tmp_path: Path,
) -> None:
    payload = _valid_payload()
    payload["candidates"] = [payload["candidates"][1]]
    paths = _write_contract(tmp_path, payload, badwords="PRIVATE-RAW-SURFACE\n")

    with pytest.raises(DictionaryProvenanceError) as captured:
        validate_dictionary_provenance(*paths)

    message = str(captured.value)
    assert "packaged literal has no approved provenance candidate" in message
    assert "PRIVATE-RAW-SURFACE" not in message


@pytest.mark.parametrize(
    ("mutation", "expected_message"),
    [
        (
            lambda payload: payload["sources"][0].update(redistribution_allowed=False),
            "packaged candidate source must allow redistribution",
        ),
        (
            lambda payload: payload["sources"][0].update(license_status="pending"),
            "packaged candidate source license must be approved",
        ),
        (
            lambda payload: payload["candidates"][0]["review"].update(status="pending"),
            "packaged candidate must have approved review",
        ),
        (
            lambda payload: payload["candidates"][0].update(target_layer="ai-candidate"),
            "ai-candidate must not be packaged",
        ),
        (
            lambda payload: payload["candidates"][0].update(classification="review"),
            "packaged candidate must be classified positive",
        ),
        (
            lambda payload: payload["candidates"][0].update(evaluation_refs=[]),
            "packaged candidate requires evaluation reference",
        ),
        (
            lambda payload: payload["candidates"][0]["review"].update(decision_reference=None),
            "approved review requires decision reference",
        ),
    ],
)
def test_unapproved_candidates_cannot_be_promoted(
    tmp_path: Path,
    mutation: Any,
    expected_message: str,
) -> None:
    payload = _valid_payload()
    mutation(payload)
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(DictionaryProvenanceError, match=expected_message):
        validate_dictionary_provenance(*paths)


@pytest.mark.parametrize(
    ("first_surface", "second_surface"),
    [("ＡＢ", "AB"), ("AB  C", "AB C")],
)
def test_normalized_surface_duplicates_are_rejected(
    tmp_path: Path,
    first_surface: str,
    second_surface: str,
) -> None:
    payload = _valid_payload()
    first = _candidate(
        candidate_id="candidate.fullwidth",
        surface=first_surface,
        canonical=first_surface,
        status="candidate",
        classification="review",
        review_status="pending",
    )
    second = _candidate(
        candidate_id="candidate.ascii",
        surface=second_surface,
        canonical=second_surface,
        status="candidate",
        classification="review",
        review_status="pending",
    )
    payload["candidates"].extend([first, second])
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(DictionaryProvenanceError, match="duplicate normalized surface"):
        validate_dictionary_provenance(*paths)


def test_manifest_rejects_incorrect_declared_normalization(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["candidates"][0]["normalized_surface"] = "incorrect"
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(DictionaryProvenanceError, match="normalized_surface does not match"):
        validate_dictionary_provenance(*paths)


def test_licensed_source_requires_reference(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["sources"][0].update(kind="licensed", reference=None)
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(DictionaryProvenanceError, match="licensed source requires reference"):
        validate_dictionary_provenance(*paths)


def test_alias_canonical_must_resolve_to_packaged_literal(tmp_path: Path) -> None:
    payload = _valid_payload()
    alias = payload["candidates"][1]
    alias["canonical"] = "없는대표어"
    alias["normalized_canonical"] = _normalized("없는대표어")
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(
        DictionaryProvenanceError, match="canonical must resolve to packaged literal"
    ):
        validate_dictionary_provenance(*paths)


def test_literal_canonical_must_match_surface(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["candidates"][0]["canonical"] = "다른대표어"
    payload["candidates"][0]["normalized_canonical"] = _normalized("다른대표어")
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(
        DictionaryProvenanceError,
        match="literal canonical must match normalized surface",
    ):
        validate_dictionary_provenance(*paths)


def test_pending_positive_does_not_redefine_registered_core_hard_negative(
    tmp_path: Path,
) -> None:
    payload = _valid_payload()
    payload["candidates"].extend(
        [
            _candidate(
                candidate_id="candidate.pending-positive",
                surface="미승인",
                canonical="미승인",
                status="candidate",
                classification="positive",
                review_status="pending",
            ),
            _candidate(
                candidate_id="candidate.hard-negative",
                surface="앞미승인뒤",
                canonical="앞미승인뒤",
                status="candidate",
                classification="hard-negative",
                review_status="approved",
            ),
        ]
    )
    paths = _write_contract(tmp_path, payload)

    summary = validate_dictionary_provenance(*paths)

    assert summary.candidate_count == 4


def test_hard_negative_cannot_contain_registered_core_surface(tmp_path: Path) -> None:
    payload = _valid_payload()
    payload["candidates"].append(
        _candidate(
            candidate_id="candidate.invalid-hard-negative",
            surface="앞금칙어뒤",
            canonical="앞금칙어뒤",
            status="candidate",
            classification="hard-negative",
            review_status="approved",
        )
    )
    paths = _write_contract(tmp_path, payload)

    with pytest.raises(
        DictionaryProvenanceError,
        match="hard-negative candidate contains registered core literal",
    ):
        validate_dictionary_provenance(*paths)


def test_cli_reports_only_candidate_ids_and_aggregate_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    payload = _valid_payload()
    payload["candidates"][0]["normalized_surface"] = "PRIVATE-NORMALIZED-SURFACE"
    manifest_path, badwords_path, aliases_path = _write_contract(tmp_path, payload)

    exit_code = main(
        [
            str(manifest_path),
            "--badwords",
            str(badwords_path),
            "--aliases",
            str(aliases_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "core.literal.unit" in captured.err
    assert "금칙어" not in captured.err
    assert "PRIVATE-NORMALIZED-SURFACE" not in captured.err
    assert captured.out == ""


def test_cli_validates_bundled_manifest(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "validated 73 candidates from 3 sources" in captured.out
    assert "packaged_literals=65" in captured.out
    assert "packaged_aliases=5" in captured.out
    assert captured.err == ""


def _valid_payload() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "unit-provenance",
        "normalization_form": "NFKC",
        "sources": [
            {
                "source_id": "koguard-unit",
                "kind": "curated",
                "name": "Koguard unit fixture",
                "reference": None,
                "revision": "unit-v1",
                "license": "LicenseRef-Koguard-Curated",
                "license_status": "approved",
                "redistribution_allowed": True,
            }
        ],
        "candidates": [
            _candidate(candidate_id="core.literal.unit", surface="금칙어", canonical="금칙어"),
            _candidate(
                candidate_id="core.alias.unit",
                surface="ㄱㅊㅇ",
                canonical="금칙어",
                representation="alias",
                matcher="exact_token",
            ),
        ],
    }


def _candidate(
    *,
    candidate_id: str,
    surface: str,
    canonical: str,
    representation: str = "literal",
    matcher: str = "exact",
    target_layer: str = "core",
    classification: str = "positive",
    status: str = "packaged",
    review_status: str = "approved",
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "surface": surface,
        "normalized_surface": _normalized(surface),
        "canonical": canonical,
        "normalized_canonical": _normalized(canonical),
        "representation": representation,
        "matcher": matcher,
        "target_layer": target_layer,
        "classification": classification,
        "status": status,
        "source_id": "koguard-unit",
        "evaluation_refs": ["test:unit"],
        "review": {
            "status": review_status,
            "decision_reference": "tests/test_dictionary_provenance.py",
            "notes": "Unit contract decision.",
        },
        "notes": "Unit candidate.",
    }


def _normalized(value: str) -> str:
    return normalize_text(value, "NFKC").text.strip()


def _write_contract(
    tmp_path: Path,
    payload: dict[str, Any],
    *,
    badwords: str = "금칙어\n",
    aliases: str = "ㄱㅊㅇ\t금칙어\texact_token\n",
) -> tuple[Path, Path, Path]:
    manifest_path = tmp_path / "dictionary-provenance.json"
    badwords_path = tmp_path / "badwords.txt"
    aliases_path = tmp_path / "aliases.tsv"
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    badwords_path.write_text(badwords, encoding="utf-8")
    aliases_path.write_text(aliases, encoding="utf-8")
    return manifest_path, badwords_path, aliases_path
