"""Loading and validation for the evaluation corpus."""

import json
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any, get_args

from evaluation.schema import (
    KNOWN_SLICES,
    OBFUSCATION_SLICES,
    EvaluationCase,
    ExpectedMatch,
    Label,
    Source,
    Split,
    Status,
)

_CORPUS_ROOT = Path(__file__).parent / "corpus"

_SOURCES = frozenset(get_args(Source))
_SPLITS: tuple[Split, ...] = get_args(Split)
_STATUSES = frozenset(get_args(Status))
_LABELS = frozenset(get_args(Label))


class CorpusError(ValueError):
    """Raised when a corpus file or case violates the annotation schema."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise CorpusError(message)


def _parse_expected_match(raw: Any, case_id: str) -> ExpectedMatch:
    _require(isinstance(raw, dict), f"{case_id}: expected_matches entries must be objects")
    missing = {"start", "end", "canonical_term", "label"} - set(raw)
    _require(not missing, f"{case_id}: expected match is missing {sorted(missing)}")

    start, end = raw["start"], raw["end"]
    _require(
        isinstance(start, int) and isinstance(end, int),
        f"{case_id}: span offsets must be integers",
    )
    _require(raw["label"] in _LABELS, f"{case_id}: unknown label {raw['label']!r}")
    _require(
        isinstance(raw["canonical_term"], str) and raw["canonical_term"].strip() != "",
        f"{case_id}: canonical_term must be a non-empty string",
    )

    return ExpectedMatch(
        start=start,
        end=end,
        canonical_term=raw["canonical_term"],
        label=raw["label"],
    )


def _parse_case(raw: Any, split: Split, path: Path) -> EvaluationCase:
    _require(isinstance(raw, dict), f"{path.name}: every case must be an object")
    case_id = raw.get("id")
    _require(
        isinstance(case_id, str) and case_id.strip() != "",
        f"{path.name}: every case needs a non-empty id",
    )
    _require("text" in raw and isinstance(raw["text"], str), f"{case_id}: text must be a string")

    slices = tuple(raw.get("slices", ()))
    _require(bool(slices), f"{case_id}: at least one slice is required")
    unknown = set(slices) - KNOWN_SLICES
    _require(not unknown, f"{case_id}: unknown slices {sorted(unknown)}")

    source = raw.get("source", "curated")
    _require(source in _SOURCES, f"{case_id}: unknown source {source!r}")

    status = raw.get("status", "final")
    _require(status in _STATUSES, f"{case_id}: unknown status {status!r}")

    declared_split = raw.get("split", split)
    _require(
        declared_split == split,
        f"{case_id}: declared split {declared_split!r} does not match its directory {split!r}",
    )

    return EvaluationCase(
        id=case_id,
        text=raw["text"],
        expected_matches=tuple(
            _parse_expected_match(entry, case_id) for entry in raw.get("expected_matches", ())
        ),
        slices=slices,
        source=source,
        license=raw.get("license", "curated"),
        split=split,
        status=status,
        single_review=bool(raw.get("single_review", True)),
        notes=raw.get("notes", ""),
    )


def validate_cases(cases: Iterable[EvaluationCase]) -> tuple[EvaluationCase, ...]:
    """Return ``cases`` unchanged, or raise :class:`CorpusError` on the first defect.

    Checks that ids are unique, spans stay inside the text and actually cover
    their canonical term, and that hard negatives carry no expected match.
    """

    materialised = tuple(cases)

    duplicates = sorted(
        case_id for case_id, count in Counter(case.id for case in materialised).items() if count > 1
    )
    _require(not duplicates, f"duplicate case ids: {duplicates}")

    for case in materialised:
        if "hard_negative" in case.slices:
            _require(
                case.expected_matches == (),
                f"{case.id}: a hard negative must not declare an expected match",
            )

        obfuscated = bool(set(case.slices) & OBFUSCATION_SLICES)
        for expected in case.expected_matches:
            _require(
                0 <= expected.start < expected.end <= len(case.text),
                f"{case.id}: span {expected.start}:{expected.end} falls outside the text",
            )
            if obfuscated:
                # The surface is written to evade the canonical spelling, so the
                # span legitimately does not contain the canonical term.
                continue
            covered = case.text[expected.start : expected.end]
            _require(
                expected.canonical_term in covered or covered in expected.canonical_term,
                f"{case.id}: span {covered!r} does not correspond to "
                f"canonical term {expected.canonical_term!r}",
            )

    return materialised


def load_split(split: Split) -> tuple[EvaluationCase, ...]:
    """Load and validate every case filed under ``split``."""

    directory = _CORPUS_ROOT / split
    cases: list[EvaluationCase] = []
    for path in sorted(directory.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CorpusError(f"failed to read corpus file: {path}") from exc

        _require(isinstance(payload, list), f"{path.name}: corpus files must hold a list of cases")
        cases.extend(_parse_case(raw, split, path) for raw in payload)

    return validate_cases(cases)


def load_all_cases() -> tuple[EvaluationCase, ...]:
    """Load every split and verify that no text leaks across the split boundary."""

    by_split: dict[Split, tuple[EvaluationCase, ...]] = {
        split: load_split(split) for split in _SPLITS
    }

    tuning_texts = {case.text for case in by_split["tuning"]}
    leaked = sorted(case.id for case in by_split["evaluation"] if case.text in tuning_texts)
    _require(not leaked, f"evaluation cases reuse tuning text: {leaked}")

    combined: Sequence[EvaluationCase] = [case for split in _SPLITS for case in by_split[split]]
    return validate_cases(combined)
