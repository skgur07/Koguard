"""Validate Koguard service-evaluation corpus files without runtime dependencies."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

CORPUS_SCHEMA_PATH = Path(__file__).with_name("corpus.schema.json")
_MAX_TEXT_LENGTH = 4096
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_DOCUMENT_FIELDS = frozenset({"schema_version", "corpus_id", "cases"})
_CASE_FIELDS = frozenset(
    {
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
)
_MATCH_FIELDS = frozenset({"start", "end", "canonical_term"})
_SOURCE_FIELDS = frozenset({"kind", "name", "reference", "revision", "redistribution_allowed"})


def _load_schema() -> dict[str, object]:
    try:
        payload: object = json.loads(CORPUS_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"failed to load corpus schema: {CORPUS_SCHEMA_PATH}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("corpus schema root must be an object")
    return cast(dict[str, object], payload)


def _schema_enum(
    schema: dict[str, object],
    definition: str,
    property_name: str,
    *nested_keys: str,
) -> frozenset[str]:
    try:
        definitions = cast(dict[str, object], schema["$defs"])
        definition_payload = cast(dict[str, object], definitions[definition])
        properties = cast(dict[str, object], definition_payload["properties"])
        property_payload = cast(dict[str, object], properties[property_name])
        for nested_key in nested_keys:
            property_payload = cast(dict[str, object], property_payload[nested_key])
        values = cast(list[object], property_payload["enum"])
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"corpus schema is missing enum {definition}.{property_name}") from exc
    if not values or any(not isinstance(value, str) for value in values):
        raise RuntimeError(f"corpus schema enum {definition}.{property_name} is invalid")
    return frozenset(cast(list[str], values))


_SCHEMA = _load_schema()
_CASE_LABELS = _schema_enum(_SCHEMA, "case", "label")
_SPLITS = _schema_enum(_SCHEMA, "case", "split")
_SLICES = _schema_enum(_SCHEMA, "case", "slices", "items")
_SOURCE_KINDS = _schema_enum(_SCHEMA, "source", "kind")


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """One validation failure that never contains corpus text."""

    path: Path
    location: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}:{self.location}: {self.message}"


class CorpusValidationError(ValueError):
    """Raised when one or more corpus files violate the annotation contract."""

    def __init__(self, issues: Sequence[ValidationIssue]) -> None:
        if not issues:
            raise ValueError("issues must not be empty")
        self.issues = tuple(issues)
        super().__init__("\n".join(str(issue) for issue in self.issues))


@dataclass(frozen=True, slots=True)
class CorpusValidationSummary:
    """Non-sensitive counts returned after successful validation."""

    file_count: int
    case_count: int
    review_case_count: int
    split_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class _SourceValues:
    kind: str | None
    reference: str | None
    revision: str | None
    redistribution_allowed: bool | None


def validate_corpus_paths(paths: Sequence[Path]) -> CorpusValidationSummary:
    """Validate JSON corpus files or directories and return aggregate counts."""

    issues: list[ValidationIssue] = []
    corpus_paths = _discover_corpus_paths(paths, issues)
    seen_ids: dict[str, tuple[Path, str]] = {}
    split_counts: Counter[str] = Counter()
    case_count = 0
    review_case_count = 0

    for path in corpus_paths:
        payload = _load_payload(path, issues)
        if payload is None:
            continue
        document_cases, document_reviews, document_splits = _validate_document(
            payload,
            path,
            seen_ids,
            issues,
        )
        case_count += document_cases
        review_case_count += document_reviews
        split_counts.update(document_splits)

    if issues:
        raise CorpusValidationError(issues)
    return CorpusValidationSummary(
        file_count=len(corpus_paths),
        case_count=case_count,
        review_case_count=review_case_count,
        split_counts=tuple(sorted(split_counts.items())),
    )


def _discover_corpus_paths(
    paths: Sequence[Path],
    issues: list[ValidationIssue],
) -> tuple[Path, ...]:
    if not paths:
        issues.append(ValidationIssue(Path("."), "$", "at least one corpus path is required"))
        return ()

    discovered: set[Path] = set()
    schema_path = CORPUS_SCHEMA_PATH.resolve()
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            discovered.update(
                candidate.resolve()
                for candidate in path.rglob("*.json")
                if candidate.resolve() != schema_path
            )
        elif path.is_file():
            if path.suffix.lower() != ".json":
                issues.append(ValidationIssue(path, "$", "corpus file must use .json extension"))
            elif path != schema_path:
                discovered.add(path)
        else:
            issues.append(ValidationIssue(path, "$", "corpus path does not exist"))

    if not discovered and not issues:
        issues.append(ValidationIssue(Path("."), "$", "no corpus JSON files found"))
    return tuple(sorted(discovered, key=lambda item: item.as_posix()))


def _load_payload(path: Path, issues: list[ValidationIssue]) -> object | None:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        return payload
    except (OSError, UnicodeError, json.JSONDecodeError):
        issues.append(ValidationIssue(path, "$", "failed to read UTF-8 JSON corpus"))
        return None


def _validate_document(
    payload: object,
    path: Path,
    seen_ids: dict[str, tuple[Path, str]],
    issues: list[ValidationIssue],
) -> tuple[int, int, Counter[str]]:
    if not isinstance(payload, dict):
        issues.append(ValidationIssue(path, "$", "corpus root must be an object"))
        return 0, 0, Counter()
    document = cast(dict[str, object], payload)
    _validate_fields(document, _DOCUMENT_FIELDS, _DOCUMENT_FIELDS, path, "$", issues)

    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        issues.append(ValidationIssue(path, "schema_version", "schema_version must equal 1"))

    corpus_id = document.get("corpus_id")
    _validate_identifier(corpus_id, path, "corpus_id", issues)

    cases_value = document.get("cases")
    if not isinstance(cases_value, list):
        issues.append(ValidationIssue(path, "cases", "cases must be an array"))
        return 0, 0, Counter()
    if not cases_value:
        issues.append(ValidationIssue(path, "cases", "cases must not be empty"))

    review_count = 0
    split_counts: Counter[str] = Counter()
    for index, case_value in enumerate(cases_value):
        label, split = _validate_case(
            case_value,
            path,
            f"cases[{index}]",
            seen_ids,
            issues,
        )
        if label == "review":
            review_count += 1
        if split in _SPLITS:
            split_counts[split] += 1
    return len(cases_value), review_count, split_counts


def _validate_case(
    payload: object,
    path: Path,
    location: str,
    seen_ids: dict[str, tuple[Path, str]],
    issues: list[ValidationIssue],
) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        issues.append(ValidationIssue(path, location, "case must be an object"))
        return None, None
    case = cast(dict[str, object], payload)
    _validate_fields(case, _CASE_FIELDS, _CASE_FIELDS, path, location, issues)

    case_id = _validate_identifier(case.get("id"), path, f"{location}.id", issues)
    if case_id is not None:
        previous = seen_ids.get(case_id)
        if previous is None:
            seen_ids[case_id] = (path, location)
        else:
            previous_path, previous_location = previous
            issues.append(
                ValidationIssue(
                    path,
                    f"{location}.id",
                    "duplicate case id "
                    f"{case_id!r}; first seen at {previous_path}:{previous_location}.id",
                )
            )

    text = _validate_string(
        case.get("text"),
        path,
        f"{location}.text",
        issues,
        allow_empty=True,
        maximum_length=_MAX_TEXT_LENGTH,
    )
    label = _validate_enum(
        case.get("label"), _CASE_LABELS, "label", path, f"{location}.label", issues
    )
    split = _validate_enum(case.get("split"), _SPLITS, "split", path, f"{location}.split", issues)
    license_name = _validate_string(
        case.get("license"),
        path,
        f"{location}.license",
        issues,
        maximum_length=128,
    )
    _validate_string(
        case.get("notes"),
        path,
        f"{location}.notes",
        issues,
        allow_empty=True,
        maximum_length=2000,
    )

    matches_value = case.get("expected_matches")
    if not isinstance(matches_value, list):
        issues.append(
            ValidationIssue(
                path, f"{location}.expected_matches", "expected_matches must be an array"
            )
        )
        matches: list[object] | None = None
    else:
        matches = matches_value
        _validate_expected_matches(matches, text, path, f"{location}.expected_matches", issues)

    if label == "positive" and matches is not None and not matches:
        issues.append(
            ValidationIssue(
                path,
                f"{location}.expected_matches",
                "positive case must contain at least one expected match",
            )
        )
    if label == "hard-negative" and matches:
        issues.append(
            ValidationIssue(
                path,
                f"{location}.expected_matches",
                "hard-negative case must not contain expected matches",
            )
        )

    _validate_slices(case.get("slices"), path, f"{location}.slices", issues)
    source = _validate_source(case.get("source"), path, f"{location}.source", issues)
    _validate_distribution_boundary(
        split,
        license_name,
        source,
        path,
        location,
        issues,
    )
    return label, split


def _validate_expected_matches(
    matches: list[object],
    text: str | None,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    previous_end = 0
    for index, payload in enumerate(matches):
        match_location = f"{location}[{index}]"
        if not isinstance(payload, dict):
            issues.append(ValidationIssue(path, match_location, "expected match must be an object"))
            continue
        match = cast(dict[str, object], payload)
        _validate_fields(match, _MATCH_FIELDS, _MATCH_FIELDS, path, match_location, issues)

        start = _validate_integer(match.get("start"), path, f"{match_location}.start", issues)
        end = _validate_integer(match.get("end"), path, f"{match_location}.end", issues)
        _validate_string(
            match.get("canonical_term"),
            path,
            f"{match_location}.canonical_term",
            issues,
            maximum_length=128,
        )
        if start is None or end is None:
            continue
        if start < 0:
            issues.append(
                ValidationIssue(path, f"{match_location}.start", "start must be non-negative")
            )
        if end <= start:
            issues.append(
                ValidationIssue(path, f"{match_location}.end", "end must be greater than start")
            )
        if text is not None and end > len(text):
            issues.append(
                ValidationIssue(
                    path,
                    f"{match_location}.end",
                    "end must not exceed text length",
                )
            )
        if index > 0 and start < previous_end:
            issues.append(
                ValidationIssue(
                    path,
                    match_location,
                    "expected matches must be sorted by start and must not overlap",
                )
            )
        previous_end = max(previous_end, end)


def _validate_slices(
    payload: object,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(payload, list):
        issues.append(ValidationIssue(path, location, "slices must be an array"))
        return
    if not payload:
        issues.append(ValidationIssue(path, location, "slices must not be empty"))
    seen: set[str] = set()
    for index, value in enumerate(payload):
        item_location = f"{location}[{index}]"
        if not isinstance(value, str) or value not in _SLICES:
            issues.append(ValidationIssue(path, item_location, f"unsupported slice: {value!r}"))
            continue
        if value in seen:
            issues.append(ValidationIssue(path, item_location, f"duplicate slice: {value!r}"))
        seen.add(value)


def _validate_source(
    payload: object,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> _SourceValues:
    if not isinstance(payload, dict):
        issues.append(ValidationIssue(path, location, "source must be an object"))
        return _SourceValues(None, None, None, None)
    source = cast(dict[str, object], payload)
    _validate_fields(source, _SOURCE_FIELDS, _SOURCE_FIELDS, path, location, issues)
    kind = _validate_enum(
        source.get("kind"), _SOURCE_KINDS, "source kind", path, f"{location}.kind", issues
    )
    _validate_string(source.get("name"), path, f"{location}.name", issues, maximum_length=200)
    reference = _validate_nullable_string(
        source.get("reference"), path, f"{location}.reference", issues, maximum_length=500
    )
    revision = _validate_nullable_string(
        source.get("revision"), path, f"{location}.revision", issues, maximum_length=200
    )
    redistribution = source.get("redistribution_allowed")
    if type(redistribution) is not bool:
        issues.append(
            ValidationIssue(
                path,
                f"{location}.redistribution_allowed",
                "redistribution_allowed must be a boolean",
            )
        )
        redistribution_value: bool | None = None
    else:
        redistribution_value = redistribution

    if kind == "licensed":
        if reference is None:
            issues.append(
                ValidationIssue(path, f"{location}.reference", "licensed source requires reference")
            )
        if revision is None:
            issues.append(
                ValidationIssue(path, f"{location}.revision", "licensed source requires revision")
            )
    if kind == "private" and (reference is not None or revision is not None):
        issues.append(
            ValidationIssue(
                path,
                location,
                "private source must not contain external reference or revision",
            )
        )
    return _SourceValues(kind, reference, revision, redistribution_value)


def _validate_distribution_boundary(
    split: str | None,
    license_name: str | None,
    source: _SourceValues,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    if split == "regression" and source.redistribution_allowed is False:
        issues.append(
            ValidationIssue(
                path,
                f"{location}.source.redistribution_allowed",
                "regression case must be redistributable",
            )
        )
    if split == "private":
        if source.kind != "private":
            issues.append(
                ValidationIssue(
                    path, f"{location}.source.kind", "private split requires private source"
                )
            )
        if source.redistribution_allowed is True:
            issues.append(
                ValidationIssue(
                    path,
                    f"{location}.source.redistribution_allowed",
                    "private split must not be redistributable",
                )
            )
        if license_name != "LicenseRef-Private":
            issues.append(
                ValidationIssue(
                    path,
                    f"{location}.license",
                    "private split must use LicenseRef-Private",
                )
            )
    elif source.kind == "private":
        issues.append(
            ValidationIssue(
                path, f"{location}.source.kind", "private source requires private split"
            )
        )
    if split != "private" and license_name == "LicenseRef-Private":
        issues.append(
            ValidationIssue(
                path, f"{location}.license", "LicenseRef-Private requires private split"
            )
        )


def _validate_fields(
    payload: dict[str, object],
    required: frozenset[str],
    allowed: frozenset[str],
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> None:
    for field_name in sorted(required - payload.keys()):
        issues.append(ValidationIssue(path, location, f"missing required field: {field_name}"))
    for field_name in sorted(payload.keys() - allowed):
        issues.append(ValidationIssue(path, location, f"unknown field: {field_name}"))


def _validate_identifier(
    payload: object,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> str | None:
    value = _validate_string(payload, path, location, issues, maximum_length=128)
    if value is not None and _ID_PATTERN.fullmatch(value) is None:
        issues.append(
            ValidationIssue(
                path,
                location,
                "identifier must use lowercase ASCII letters, digits, dot, underscore, or hyphen",
            )
        )
        return None
    return value


def _validate_enum(
    payload: object,
    allowed: frozenset[str],
    enum_name: str,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> str | None:
    if not isinstance(payload, str) or payload not in allowed:
        issues.append(ValidationIssue(path, location, f"unsupported {enum_name}: {payload!r}"))
        return None
    return payload


def _validate_integer(
    payload: object,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
) -> int | None:
    if type(payload) is not int:
        issues.append(ValidationIssue(path, location, "value must be an integer"))
        return None
    return payload


def _validate_string(
    payload: object,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
    *,
    allow_empty: bool = False,
    maximum_length: int,
) -> str | None:
    if not isinstance(payload, str):
        issues.append(ValidationIssue(path, location, "value must be a string"))
        return None
    if not allow_empty and not payload:
        issues.append(ValidationIssue(path, location, "value must not be empty"))
        return None
    if len(payload) > maximum_length:
        issues.append(
            ValidationIssue(path, location, f"value exceeds maximum length {maximum_length}")
        )
    try:
        payload.encode("utf-8")
    except UnicodeEncodeError:
        issues.append(
            ValidationIssue(path, location, "value contains an invalid Unicode surrogate")
        )
        return None
    return payload


def _validate_nullable_string(
    payload: object,
    path: Path,
    location: str,
    issues: list[ValidationIssue],
    *,
    maximum_length: int,
) -> str | None:
    if payload is None:
        return None
    return _validate_string(payload, path, location, issues, maximum_length=maximum_length)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="JSON corpus files or directories")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate corpus paths and print only non-sensitive aggregate counts."""

    arguments = _parser().parse_args(argv)
    try:
        summary = validate_corpus_paths(arguments.paths)
    except CorpusValidationError as exc:
        for issue in exc.issues:
            print(issue, file=sys.stderr)
        return 1

    file_label = "file" if summary.file_count == 1 else "files"
    split_summary = ", ".join(f"{name}={count}" for name, count in summary.split_counts)
    print(
        f"validated {summary.case_count} cases in {summary.file_count} {file_label}; "
        f"review={summary.review_case_count}; {split_summary}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
