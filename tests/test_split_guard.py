"""Contract tests for PF-004 corpus split isolation."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from evaluation.split_guard import (
    DEFAULT_SPLIT_MANIFEST_PATH,
    SPLIT_MANIFEST_SCHEMA_PATH,
    SplitGuardError,
    main,
    validate_split_manifest,
)

_PROVISIONAL_CORPUS = Path("evaluation/corpus/provisional-ablation.json")


def test_split_manifest_schema_is_versioned_and_closed() -> None:
    schema = json.loads(SPLIT_MANIFEST_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["additionalProperties"] is False
    assert schema["$defs"]["assignment"]["additionalProperties"] is False
    assert set(schema["$defs"]["assignment"]["required"]) == {
        "case_id",
        "corpus_id",
        "split",
    }


def test_checked_manifest_matches_public_regression_corpus() -> None:
    summary = validate_split_manifest(
        DEFAULT_SPLIT_MANIFEST_PATH,
        [_PROVISIONAL_CORPUS],
        repository_root=Path.cwd(),
    )

    assert summary.manifest_id == "koguard-corpus-splits"
    assert summary.manifest_version == 1
    assert summary.case_count == 20
    assert summary.split_counts == (("regression", 20),)
    assert summary.direct_leak_count == 0
    assert summary.normalized_leak_count == 0


def test_tuning_and_hidden_direct_duplicate_is_rejected_without_text_leak(
    tmp_path: Path,
) -> None:
    secret_text = "원문-절대-출력-금지"
    tuning = _corpus("tuning-corpus", "tuning-case", "tuning", secret_text)
    evaluation = _corpus("evaluation-corpus", "evaluation-case", "evaluation", secret_text)
    tuning_path = _write_json(tmp_path / "tuning.json", tuning)
    protected_root = tmp_path / "protected"
    protected_root.mkdir()
    evaluation_path = _write_json(protected_root / "evaluation.json", evaluation)
    manifest = _manifest(
        [
            _assignment("tuning-corpus", "tuning-case", "tuning"),
            _assignment("evaluation-corpus", "evaluation-case", "evaluation"),
        ]
    )
    manifest_path = _write_json(tmp_path / "manifest.json", manifest)

    with pytest.raises(SplitGuardError, match="direct text leakage") as captured:
        validate_split_manifest(
            manifest_path,
            [tuning_path, evaluation_path],
            repository_root=tmp_path / "public-repository",
        )

    assert secret_text not in str(captured.value)
    assert "tuning-case" in str(captured.value)
    assert "evaluation-case" in str(captured.value)


def test_tuning_and_hidden_normalized_variant_is_rejected(tmp_path: Path) -> None:
    tuning = _corpus("tuning-corpus", "tuning-case", "tuning", "시 발!!!")
    evaluation = _corpus("evaluation-corpus", "evaluation-case", "evaluation", "시발")
    tuning_path = _write_json(tmp_path / "tuning.json", tuning)
    evaluation_path = _write_json(tmp_path / "protected-evaluation.json", evaluation)
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        _manifest(
            [
                _assignment("tuning-corpus", "tuning-case", "tuning"),
                _assignment("evaluation-corpus", "evaluation-case", "evaluation"),
            ]
        ),
    )

    with pytest.raises(SplitGuardError, match="normalized text leakage"):
        validate_split_manifest(
            manifest_path,
            [tuning_path, evaluation_path],
            repository_root=tmp_path / "public-repository",
        )


@pytest.mark.parametrize("protected_split", ["evaluation", "private"])
def test_protected_raw_corpus_inside_repository_is_rejected(
    tmp_path: Path,
    protected_split: str,
) -> None:
    repository_root = tmp_path / "repository"
    repository_root.mkdir()
    corpus_id = f"{protected_split}-corpus"
    case_id = f"{protected_split}-case"
    corpus_path = _write_json(
        repository_root / f"{protected_split}.json",
        _corpus(corpus_id, case_id, protected_split, "보호 원문"),
    )
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        _manifest([_assignment(corpus_id, case_id, protected_split)]),
    )

    with pytest.raises(SplitGuardError, match="protected raw corpus must be outside repository"):
        validate_split_manifest(
            manifest_path,
            [corpus_path],
            repository_root=repository_root,
        )


def test_manifest_assignment_must_match_case_split(tmp_path: Path) -> None:
    corpus_path = _write_json(
        tmp_path / "tuning.json",
        _corpus("tuning-corpus", "stable-case", "tuning", "테스트 문장"),
    )
    manifest_path = _write_json(
        tmp_path / "manifest.json",
        _manifest([_assignment("tuning-corpus", "stable-case", "evaluation")]),
    )

    with pytest.raises(SplitGuardError, match="manifest assignment does not match corpus"):
        validate_split_manifest(
            manifest_path,
            [corpus_path],
            repository_root=tmp_path / "public-repository",
        )


def test_assignment_change_requires_manifest_version_increment(tmp_path: Path) -> None:
    corpus_path = _write_json(
        tmp_path / "tuning.json",
        _corpus("tuning-corpus", "stable-case", "tuning", "테스트 문장"),
    )
    previous = _manifest([_assignment("tuning-corpus", "stable-case", "regression")])
    current = copy.deepcopy(previous)
    current["change_reason"] = "Move the case into tuning."
    current["assignments"][0]["split"] = "tuning"
    previous_path = _write_json(tmp_path / "previous.json", previous)
    current_path = _write_json(tmp_path / "current.json", current)

    with pytest.raises(SplitGuardError, match="manifest version must increase"):
        validate_split_manifest(
            current_path,
            [corpus_path],
            repository_root=tmp_path / "public-repository",
            previous_manifest_path=previous_path,
        )


def test_cli_reports_only_non_sensitive_split_counts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(
        [
            str(DEFAULT_SPLIT_MANIFEST_PATH),
            str(_PROVISIONAL_CORPUS),
            "--repository-root",
            str(Path.cwd()),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "manifest=koguard-corpus-splits@1" in captured.out
    assert "regression=20" in captured.out
    assert "leaks=0" in captured.out
    assert captured.err == ""


def _manifest(assignments: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "manifest_id": "unit-split-manifest",
        "manifest_version": 1,
        "change_reason": "Initial stable split assignment.",
        "normalization_version": "nfkc-casefold-strip-pzc-repeat-v1",
        "assignments": assignments,
    }


def _assignment(corpus_id: str, case_id: str, split: str) -> dict[str, str]:
    return {"corpus_id": corpus_id, "case_id": case_id, "split": split}


def _corpus(corpus_id: str, case_id: str, split: str, text: str) -> dict[str, Any]:
    private = split == "private"
    return {
        "schema_version": 1,
        "corpus_id": corpus_id,
        "cases": [
            {
                "id": case_id,
                "text": text,
                "label": "hard-negative",
                "expected_matches": [],
                "slices": ["domain-term"],
                "source": {
                    "kind": "private" if private else "curated",
                    "name": "Private fixture" if private else "Koguard test fixture",
                    "reference": None,
                    "revision": None,
                    "redistribution_allowed": not private,
                },
                "license": "LicenseRef-Private" if private else "MIT",
                "split": split,
                "notes": "Split guard contract fixture.",
            }
        ],
    }


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path
