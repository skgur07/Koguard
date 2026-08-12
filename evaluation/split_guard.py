"""Enforce stable corpus splits and prevent tuning-to-evaluation leakage."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths

SPLIT_MANIFEST_SCHEMA_PATH = Path(__file__).with_name("split-manifest.schema.json")
DEFAULT_SPLIT_MANIFEST_PATH = Path(__file__).with_name("splits") / "corpus-splits.v1.json"
NORMALIZATION_VERSION = "nfkc-casefold-strip-pzc-repeat-v1"
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SPLITS = frozenset({"regression", "tuning", "evaluation", "private"})
_VISIBLE_TO_RULE_AUTHORS = frozenset({"regression", "tuning"})
_PROTECTED_SPLITS = frozenset({"evaluation", "private"})
_MANIFEST_FIELDS = frozenset(
    {
        "schema_version",
        "manifest_id",
        "manifest_version",
        "change_reason",
        "normalization_version",
        "assignments",
    }
)
_ASSIGNMENT_FIELDS = frozenset({"case_id", "corpus_id", "split"})


@dataclass(frozen=True, slots=True)
class SplitGuardSummary:
    """Non-sensitive split validation totals."""

    manifest_id: str
    manifest_version: int
    case_count: int
    split_counts: tuple[tuple[str, int], ...]
    direct_leak_count: int
    normalized_leak_count: int


class SplitGuardError(ValueError):
    """Raised for split policy failures without embedding corpus text."""

    def __init__(self, issues: Sequence[str]) -> None:
        if not issues:
            raise ValueError("issues must not be empty")
        self.issues = tuple(issues)
        super().__init__("\n".join(self.issues))


@dataclass(frozen=True, slots=True)
class _Assignment:
    corpus_id: str
    case_id: str
    split: str


@dataclass(frozen=True, slots=True)
class _Manifest:
    manifest_id: str
    manifest_version: int
    change_reason: str
    normalization_version: str
    assignments: tuple[_Assignment, ...]


@dataclass(frozen=True, slots=True)
class _CaseRecord:
    path: Path
    corpus_id: str
    case_id: str
    split: str
    text: str


def validate_split_manifest(
    manifest_path: Path,
    corpus_paths: Sequence[Path],
    *,
    repository_root: Path,
    previous_manifest_path: Path | None = None,
) -> SplitGuardSummary:
    """Validate manifest membership, storage boundaries, and cross-split leakage."""

    manifest = _load_manifest(manifest_path)
    previous = _load_manifest(previous_manifest_path) if previous_manifest_path else None
    issues: list[str] = []
    if previous is not None:
        _validate_manifest_change(previous, manifest, issues)

    validate_corpus_paths(corpus_paths)
    records = _load_corpus_records(corpus_paths)
    assignments = {assignment.case_id: assignment for assignment in manifest.assignments}
    materialized_ids = {record.case_id for record in records}

    for record in records:
        assignment = assignments.get(record.case_id)
        if assignment is None:
            issues.append(f"case {record.case_id!r} is missing from split manifest")
            continue
        if (assignment.corpus_id, assignment.split) != (record.corpus_id, record.split):
            issues.append(
                "manifest assignment does not match corpus for case "
                f"{record.case_id!r}: manifest={assignment.corpus_id}/{assignment.split}, "
                f"corpus={record.corpus_id}/{record.split}"
            )
        if record.split in _PROTECTED_SPLITS and _is_within(record.path, repository_root):
            issues.append(
                "protected raw corpus must be outside repository for case "
                f"{record.case_id!r} ({record.split})"
            )

    for case_id in sorted(assignments.keys() - materialized_ids):
        issues.append(f"manifest case {case_id!r} has no materialized corpus record")

    direct_leaks, normalized_leaks = _find_leaks(records)
    for visible, hidden in direct_leaks:
        issues.append(
            "direct text leakage between visible and hidden evaluation cases: "
            f"{visible.case_id!r} ({visible.split}) and {hidden.case_id!r} (evaluation)"
        )
    for visible, hidden in normalized_leaks:
        issues.append(
            "normalized text leakage between visible and hidden evaluation cases: "
            f"{visible.case_id!r} ({visible.split}) and {hidden.case_id!r} (evaluation); "
            f"normalization={NORMALIZATION_VERSION}"
        )

    if issues:
        raise SplitGuardError(issues)

    split_counts = Counter(record.split for record in records)
    return SplitGuardSummary(
        manifest_id=manifest.manifest_id,
        manifest_version=manifest.manifest_version,
        case_count=len(records),
        split_counts=tuple(sorted(split_counts.items())),
        direct_leak_count=0,
        normalized_leak_count=0,
    )


def _load_manifest(path: Path) -> _Manifest:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SplitGuardError((f"failed to read split manifest: {path}",)) from exc
    if not isinstance(payload, dict):
        raise SplitGuardError(("split manifest root must be an object",))
    document = cast(dict[str, object], payload)
    issues: list[str] = []
    _validate_closed_fields(document, _MANIFEST_FIELDS, "manifest", issues)

    schema_version = document.get("schema_version")
    if type(schema_version) is not int or schema_version != 1:
        issues.append("split manifest schema_version must equal 1")
    manifest_id = _identifier(document.get("manifest_id"), "manifest_id", issues)
    manifest_version = document.get("manifest_version")
    if type(manifest_version) is not int or manifest_version < 1:
        issues.append("manifest_version must be an integer of at least 1")
        manifest_version_value = 0
    else:
        manifest_version_value = manifest_version
    change_reason = document.get("change_reason")
    if not isinstance(change_reason, str) or not change_reason.strip():
        issues.append("change_reason must be a non-empty string")
        change_reason_value = ""
    elif len(change_reason) > 2000:
        issues.append("change_reason exceeds maximum length 2000")
        change_reason_value = change_reason
    else:
        change_reason_value = change_reason
    normalization_version = document.get("normalization_version")
    if normalization_version != NORMALIZATION_VERSION:
        issues.append(f"normalization_version must equal {NORMALIZATION_VERSION!r}")

    assignments_payload = document.get("assignments")
    assignments: list[_Assignment] = []
    seen_ids: set[str] = set()
    if not isinstance(assignments_payload, list) or not assignments_payload:
        issues.append("assignments must be a non-empty array")
    else:
        for index, raw_assignment in enumerate(assignments_payload):
            location = f"assignments[{index}]"
            if not isinstance(raw_assignment, dict):
                issues.append(f"{location} must be an object")
                continue
            assignment = cast(dict[str, object], raw_assignment)
            _validate_closed_fields(assignment, _ASSIGNMENT_FIELDS, location, issues)
            corpus_id = _identifier(assignment.get("corpus_id"), f"{location}.corpus_id", issues)
            case_id = _identifier(assignment.get("case_id"), f"{location}.case_id", issues)
            split = assignment.get("split")
            if not isinstance(split, str) or split not in _SPLITS:
                issues.append(f"{location}.split is unsupported")
            if case_id is not None:
                if case_id in seen_ids:
                    issues.append(f"duplicate manifest case id {case_id!r}")
                seen_ids.add(case_id)
            if corpus_id is not None and case_id is not None and isinstance(split, str):
                if split in _SPLITS:
                    assignments.append(_Assignment(corpus_id, case_id, split))

    if issues:
        raise SplitGuardError(issues)
    assert manifest_id is not None
    assert isinstance(normalization_version, str)
    return _Manifest(
        manifest_id=manifest_id,
        manifest_version=manifest_version_value,
        change_reason=change_reason_value,
        normalization_version=normalization_version,
        assignments=tuple(assignments),
    )


def _validate_manifest_change(
    previous: _Manifest,
    current: _Manifest,
    issues: list[str],
) -> None:
    if previous.manifest_id != current.manifest_id:
        issues.append("previous and current manifest_id must match")
        return
    changed = (
        previous.assignments != current.assignments
        or previous.normalization_version != current.normalization_version
    )
    if changed and current.manifest_version <= previous.manifest_version:
        issues.append("manifest version must increase when assignments or normalization change")


def _discover_corpus_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    files: set[Path] = set()
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            files.update(candidate.resolve() for candidate in path.rglob("*.json"))
        elif path.is_file():
            files.add(path)
    return tuple(sorted(files, key=lambda item: item.as_posix()))


def _load_corpus_records(paths: Sequence[Path]) -> tuple[_CaseRecord, ...]:
    records: list[_CaseRecord] = []
    for path in _discover_corpus_files(paths):
        payload = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
        corpus_id = cast(str, payload["corpus_id"])
        for raw_case in cast(list[dict[str, Any]], payload["cases"]):
            records.append(
                _CaseRecord(
                    path=path,
                    corpus_id=corpus_id,
                    case_id=cast(str, raw_case["id"]),
                    split=cast(str, raw_case["split"]),
                    text=cast(str, raw_case["text"]),
                )
            )
    return tuple(records)


def _find_leaks(
    records: Sequence[_CaseRecord],
) -> tuple[
    tuple[tuple[_CaseRecord, _CaseRecord], ...], tuple[tuple[_CaseRecord, _CaseRecord], ...]
]:
    visible_direct: dict[bytes, list[_CaseRecord]] = defaultdict(list)
    visible_normalized: dict[bytes, list[_CaseRecord]] = defaultdict(list)
    for record in records:
        if record.split not in _VISIBLE_TO_RULE_AUTHORS:
            continue
        visible_direct[_fingerprint(record.text)].append(record)
        visible_normalized[_fingerprint(_normalize_for_leak_check(record.text))].append(record)

    direct: list[tuple[_CaseRecord, _CaseRecord]] = []
    normalized: list[tuple[_CaseRecord, _CaseRecord]] = []
    for hidden in records:
        if hidden.split != "evaluation":
            continue
        direct_matches = visible_direct.get(_fingerprint(hidden.text), ())
        direct.extend((visible, hidden) for visible in direct_matches)
        direct_case_ids = {visible.case_id for visible in direct_matches}
        normalized_matches = visible_normalized.get(
            _fingerprint(_normalize_for_leak_check(hidden.text)), ()
        )
        normalized.extend(
            (visible, hidden)
            for visible in normalized_matches
            if visible.case_id not in direct_case_ids
        )
    return tuple(direct), tuple(normalized)


def _normalize_for_leak_check(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    retained = (
        character
        for character in normalized
        if not unicodedata.category(character).startswith(("P", "Z"))
        and unicodedata.category(character) != "Cf"
    )
    collapsed: list[str] = []
    for character in retained:
        if not collapsed or collapsed[-1] != character:
            collapsed.append(character)
    return "".join(collapsed)


def _fingerprint(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _validate_closed_fields(
    payload: dict[str, object],
    allowed: frozenset[str],
    location: str,
    issues: list[str],
) -> None:
    for field_name in sorted(allowed - payload.keys()):
        issues.append(f"{location} is missing required field {field_name!r}")
    for field_name in sorted(payload.keys() - allowed):
        issues.append(f"{location} contains unknown field {field_name!r}")


def _identifier(payload: object, location: str, issues: list[str]) -> str | None:
    if not isinstance(payload, str) or _ID_PATTERN.fullmatch(payload) is None:
        issues.append(f"{location} must be a stable lowercase ASCII identifier")
        return None
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corpus", nargs="+", type=Path)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--previous-manifest", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the split guard and print only aggregate counts."""

    arguments = _parser().parse_args(argv)
    try:
        summary = validate_split_manifest(
            arguments.manifest,
            arguments.corpus,
            repository_root=arguments.repository_root,
            previous_manifest_path=arguments.previous_manifest,
        )
    except (CorpusValidationError, SplitGuardError) as exc:
        print(exc, file=sys.stderr)
        return 1
    split_summary = ", ".join(f"{name}={count}" for name, count in summary.split_counts)
    print(
        f"manifest={summary.manifest_id}@{summary.manifest_version}; "
        f"cases={summary.case_count}; {split_summary}; "
        f"leaks={summary.direct_leak_count + summary.normalized_leak_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
