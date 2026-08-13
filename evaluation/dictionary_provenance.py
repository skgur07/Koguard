"""Validate dictionary provenance and packaged-data promotion boundaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from koguard.engine.normalizer import normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DICTIONARY_PROVENANCE_SCHEMA_PATH = Path(__file__).with_name("dictionary-provenance.schema.json")
DICTIONARY_PROVENANCE_PATH = Path(__file__).with_name("dictionary-provenance.v1.json")
DEFAULT_BADWORDS_PATH = PROJECT_ROOT / "src" / "koguard" / "data" / "badwords.txt"
DEFAULT_ALIASES_PATH = PROJECT_ROOT / "src" / "koguard" / "data" / "aliases.tsv"

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_DOCUMENT_FIELDS = frozenset(
    {"schema_version", "manifest_id", "normalization_form", "sources", "candidates"}
)
_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "kind",
        "name",
        "reference",
        "revision",
        "license",
        "license_status",
        "redistribution_allowed",
    }
)
_CANDIDATE_FIELDS = frozenset(
    {
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
)
_REVIEW_FIELDS = frozenset({"status", "decision_reference", "notes"})
_SOURCE_KINDS = frozenset({"curated", "licensed"})
_REPRESENTATIONS = frozenset({"literal", "alias"})
_MATCHERS = frozenset({"exact", "exact_token", "token_prefix"})
_TARGET_LAYERS = frozenset({"core", "ai-candidate"})
_CLASSIFICATIONS = frozenset({"positive", "hard-negative", "review"})
_STATUSES = frozenset({"candidate", "packaged", "rejected"})
_REVIEW_STATUSES = frozenset({"pending", "approved", "rejected"})
_LICENSE_STATUSES = frozenset({"pending", "approved", "rejected"})


@dataclass(frozen=True, slots=True)
class ProvenanceIssue:
    """One validation failure that identifies metadata but never a candidate surface."""

    path: Path
    candidate_id: str | None
    location: str
    message: str

    def __str__(self) -> str:
        identity = f" [{self.candidate_id}]" if self.candidate_id is not None else ""
        return f"{self.path}:{self.location}{identity}: {self.message}"


class DictionaryProvenanceError(ValueError):
    """Raised when dictionary provenance violates the promotion contract."""

    def __init__(self, issues: list[ProvenanceIssue]) -> None:
        if not issues:
            raise ValueError("issues must not be empty")
        self.issues = tuple(issues)
        super().__init__("\n".join(str(issue) for issue in issues))


@dataclass(frozen=True, slots=True)
class DictionaryProvenanceSummary:
    """Non-sensitive aggregate counts returned by successful validation."""

    source_count: int
    candidate_count: int
    packaged_literal_count: int
    packaged_alias_count: int
    ai_candidate_count: int
    pending_review_count: int


@dataclass(frozen=True, slots=True)
class _Source:
    source_id: str
    license_status: str
    redistribution_allowed: bool


@dataclass(frozen=True, slots=True)
class _Candidate:
    candidate_id: str
    surface: str
    normalized_surface: str
    canonical: str
    normalized_canonical: str
    representation: str
    matcher: str
    target_layer: str
    classification: str
    status: str
    source_id: str
    evaluation_refs: tuple[str, ...]
    review_status: str
    review_decision_reference: str | None


def validate_dictionary_provenance(
    manifest_path: Path,
    badwords_path: Path = DEFAULT_BADWORDS_PATH,
    aliases_path: Path = DEFAULT_ALIASES_PATH,
) -> DictionaryProvenanceSummary:
    """Validate one provenance manifest against exact packaged dictionary files."""

    issues: list[ProvenanceIssue] = []
    payload = _load_json(manifest_path, issues)
    badwords = _read_dictionary_lines(badwords_path, "badwords", issues)
    aliases = _read_alias_lines(aliases_path, issues)
    if payload is None:
        raise DictionaryProvenanceError(issues)

    sources, candidates = _validate_manifest(payload, manifest_path, issues)
    _validate_candidates(candidates, sources, badwords, aliases, manifest_path, issues)
    if issues:
        raise DictionaryProvenanceError(issues)

    return DictionaryProvenanceSummary(
        source_count=len(sources),
        candidate_count=len(candidates),
        packaged_literal_count=sum(
            candidate.status == "packaged" and candidate.representation == "literal"
            for candidate in candidates
        ),
        packaged_alias_count=sum(
            candidate.status == "packaged" and candidate.representation == "alias"
            for candidate in candidates
        ),
        ai_candidate_count=sum(
            candidate.target_layer == "ai-candidate" for candidate in candidates
        ),
        pending_review_count=sum(candidate.review_status == "pending" for candidate in candidates),
    )


def _load_json(path: Path, issues: list[ProvenanceIssue]) -> object | None:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
        return payload
    except (OSError, UnicodeError, json.JSONDecodeError):
        issues.append(ProvenanceIssue(path, None, "$", "failed to read UTF-8 JSON manifest"))
        return None


def _read_dictionary_lines(
    path: Path,
    label: str,
    issues: list[ProvenanceIssue],
) -> tuple[str, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        issues.append(ProvenanceIssue(path, None, "$", f"failed to read UTF-8 {label} file"))
        return ()
    values = tuple(
        line.strip() for line in lines if line.strip() and not line.strip().startswith("#")
    )
    if not values:
        issues.append(ProvenanceIssue(path, None, "$", f"{label} file must not be empty"))
    return values


def _read_alias_lines(
    path: Path,
    issues: list[ProvenanceIssue],
) -> tuple[tuple[str, str, str], ...]:
    lines = _read_dictionary_lines(path, "aliases", issues)
    aliases: list[tuple[str, str, str]] = []
    for line_number, line in enumerate(lines, start=1):
        fields = tuple(field.strip() for field in line.split("\t"))
        if len(fields) != 3 or not all(fields):
            issues.append(
                ProvenanceIssue(
                    path,
                    None,
                    f"line[{line_number}]",
                    "alias line must have three tab-separated fields",
                )
            )
            continue
        aliases.append((fields[0], fields[1], fields[2]))
    return tuple(aliases)


def _validate_manifest(
    payload: object,
    path: Path,
    issues: list[ProvenanceIssue],
) -> tuple[dict[str, _Source], tuple[_Candidate, ...]]:
    if not isinstance(payload, dict):
        issues.append(ProvenanceIssue(path, None, "$", "manifest root must be an object"))
        return {}, ()
    document = cast(dict[str, object], payload)
    _validate_fields(document, _DOCUMENT_FIELDS, path, None, "$", issues)
    if type(document.get("schema_version")) is not int or document.get("schema_version") != 1:
        issues.append(ProvenanceIssue(path, None, "schema_version", "schema_version must equal 1"))
    _identifier(document.get("manifest_id"), path, None, "manifest_id", issues)
    if document.get("normalization_form") != "NFKC":
        issues.append(
            ProvenanceIssue(path, None, "normalization_form", "normalization_form must equal NFKC")
        )

    sources = _validate_sources(document.get("sources"), path, issues)
    candidates = _validate_candidate_records(document.get("candidates"), path, issues)
    return sources, candidates


def _validate_sources(
    payload: object,
    path: Path,
    issues: list[ProvenanceIssue],
) -> dict[str, _Source]:
    if not isinstance(payload, list) or not payload:
        issues.append(ProvenanceIssue(path, None, "sources", "sources must be a non-empty array"))
        return {}
    sources: dict[str, _Source] = {}
    for index, item in enumerate(payload):
        location = f"sources[{index}]"
        if not isinstance(item, dict):
            issues.append(ProvenanceIssue(path, None, location, "source must be an object"))
            continue
        source = cast(dict[str, object], item)
        _validate_fields(source, _SOURCE_FIELDS, path, None, location, issues)
        source_id = _identifier(
            source.get("source_id"), path, None, f"{location}.source_id", issues
        )
        kind = _enum(source.get("kind"), _SOURCE_KINDS, path, None, f"{location}.kind", issues)
        _text(source.get("name"), path, None, f"{location}.name", issues)
        reference = _nullable_text(
            source.get("reference"), path, None, f"{location}.reference", issues
        )
        _text(source.get("revision"), path, None, f"{location}.revision", issues)
        _text(source.get("license"), path, None, f"{location}.license", issues)
        license_status = _enum(
            source.get("license_status"),
            _LICENSE_STATUSES,
            path,
            None,
            f"{location}.license_status",
            issues,
        )
        if kind == "licensed" and reference is None:
            issues.append(
                ProvenanceIssue(
                    path,
                    None,
                    f"{location}.reference",
                    "licensed source requires reference",
                )
            )
        redistribution = source.get("redistribution_allowed")
        if type(redistribution) is not bool:
            issues.append(
                ProvenanceIssue(
                    path,
                    None,
                    f"{location}.redistribution_allowed",
                    "redistribution_allowed must be boolean",
                )
            )
            continue
        if source_id is None or license_status is None:
            continue
        if source_id in sources:
            issues.append(
                ProvenanceIssue(path, None, f"{location}.source_id", "duplicate source id")
            )
            continue
        sources[source_id] = _Source(source_id, license_status, redistribution)
    return sources


def _validate_candidate_records(
    payload: object,
    path: Path,
    issues: list[ProvenanceIssue],
) -> tuple[_Candidate, ...]:
    if not isinstance(payload, list) or not payload:
        issues.append(
            ProvenanceIssue(path, None, "candidates", "candidates must be a non-empty array")
        )
        return ()
    candidates: list[_Candidate] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload):
        location = f"candidates[{index}]"
        if not isinstance(item, dict):
            issues.append(ProvenanceIssue(path, None, location, "candidate must be an object"))
            continue
        candidate = cast(dict[str, object], item)
        candidate_id_value = candidate.get("candidate_id")
        candidate_id = candidate_id_value if isinstance(candidate_id_value, str) else None
        _validate_fields(candidate, _CANDIDATE_FIELDS, path, candidate_id, location, issues)
        validated_id = _identifier(
            candidate_id_value, path, candidate_id, f"{location}.candidate_id", issues
        )
        values = (
            _text(candidate.get("surface"), path, candidate_id, f"{location}.surface", issues),
            _text(
                candidate.get("normalized_surface"),
                path,
                candidate_id,
                f"{location}.normalized_surface",
                issues,
            ),
            _text(candidate.get("canonical"), path, candidate_id, f"{location}.canonical", issues),
            _text(
                candidate.get("normalized_canonical"),
                path,
                candidate_id,
                f"{location}.normalized_canonical",
                issues,
            ),
            _enum(
                candidate.get("representation"),
                _REPRESENTATIONS,
                path,
                candidate_id,
                f"{location}.representation",
                issues,
            ),
            _enum(
                candidate.get("matcher"),
                _MATCHERS,
                path,
                candidate_id,
                f"{location}.matcher",
                issues,
            ),
            _enum(
                candidate.get("target_layer"),
                _TARGET_LAYERS,
                path,
                candidate_id,
                f"{location}.target_layer",
                issues,
            ),
            _enum(
                candidate.get("classification"),
                _CLASSIFICATIONS,
                path,
                candidate_id,
                f"{location}.classification",
                issues,
            ),
            _enum(
                candidate.get("status"),
                _STATUSES,
                path,
                candidate_id,
                f"{location}.status",
                issues,
            ),
            _identifier(
                candidate.get("source_id"),
                path,
                candidate_id,
                f"{location}.source_id",
                issues,
            ),
        )
        evaluation_refs = _string_list(
            candidate.get("evaluation_refs"),
            path,
            candidate_id,
            f"{location}.evaluation_refs",
            issues,
        )
        review_status, review_decision_reference = _validate_review(
            candidate.get("review"), path, candidate_id, f"{location}.review", issues
        )
        _text(
            candidate.get("notes"),
            path,
            candidate_id,
            f"{location}.notes",
            issues,
            allow_empty=True,
        )
        if (
            validated_id is None
            or evaluation_refs is None
            or review_status is None
            or any(value is None for value in values)
        ):
            continue
        if validated_id in seen_ids:
            issues.append(
                ProvenanceIssue(
                    path, validated_id, f"{location}.candidate_id", "duplicate candidate id"
                )
            )
            continue
        seen_ids.add(validated_id)
        (
            surface,
            normalized_surface,
            canonical,
            normalized_canonical,
            representation,
            matcher,
            target_layer,
            classification,
            status,
            source_id,
        ) = cast(tuple[str, str, str, str, str, str, str, str, str, str], values)
        candidates.append(
            _Candidate(
                validated_id,
                surface,
                normalized_surface,
                canonical,
                normalized_canonical,
                representation,
                matcher,
                target_layer,
                classification,
                status,
                source_id,
                evaluation_refs,
                review_status,
                review_decision_reference,
            )
        )
    return tuple(candidates)


def _validate_review(
    payload: object,
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
) -> tuple[str | None, str | None]:
    if not isinstance(payload, dict):
        issues.append(ProvenanceIssue(path, candidate_id, location, "review must be an object"))
        return None, None
    review = cast(dict[str, object], payload)
    _validate_fields(review, _REVIEW_FIELDS, path, candidate_id, location, issues)
    status = _enum(
        review.get("status"), _REVIEW_STATUSES, path, candidate_id, f"{location}.status", issues
    )
    decision_reference = _nullable_text(
        review.get("decision_reference"),
        path,
        candidate_id,
        f"{location}.decision_reference",
        issues,
    )
    _text(
        review.get("notes"),
        path,
        candidate_id,
        f"{location}.notes",
        issues,
        allow_empty=True,
    )
    if status == "approved" and decision_reference is None:
        issues.append(
            ProvenanceIssue(
                path,
                candidate_id,
                f"{location}.decision_reference",
                "approved review requires decision reference",
            )
        )
    return status, decision_reference


def _validate_candidates(
    candidates: tuple[_Candidate, ...],
    sources: dict[str, _Source],
    badwords: tuple[str, ...],
    aliases: tuple[tuple[str, str, str], ...],
    path: Path,
    issues: list[ProvenanceIssue],
) -> None:
    all_literals = {
        candidate.normalized_surface: candidate
        for candidate in candidates
        if candidate.representation == "literal" and candidate.status != "rejected"
    }
    packaged_literals = {
        _normalize(candidate.surface): candidate
        for candidate in candidates
        if candidate.status == "packaged" and candidate.representation == "literal"
    }
    required_literals = {_normalize(value) for value in badwords}
    required_literals.update(_normalize(canonical) for _, canonical, _ in aliases)
    registered_core_literals = {
        candidate.normalized_surface
        for candidate in candidates
        if candidate.target_layer == "core"
        and candidate.classification == "positive"
        and candidate.status == "packaged"
        and candidate.representation == "literal"
    }
    seen_normalized: dict[str, str] = {}
    packaged_keys: dict[tuple[str, str, str], _Candidate] = {}

    for candidate in candidates:
        if candidate.normalized_surface != _normalize(candidate.surface):
            _candidate_issue(
                path,
                candidate,
                "normalized_surface",
                "normalized_surface does not match NFKC",
                issues,
            )
        if candidate.normalized_canonical != _normalize(candidate.canonical):
            _candidate_issue(
                path,
                candidate,
                "normalized_canonical",
                "normalized_canonical does not match NFKC",
                issues,
            )
        previous_id = seen_normalized.get(candidate.normalized_surface)
        if previous_id is not None:
            _candidate_issue(
                path,
                candidate,
                "normalized_surface",
                f"duplicate normalized surface; first candidate={previous_id}",
                issues,
            )
        else:
            seen_normalized[candidate.normalized_surface] = candidate.candidate_id

        source = sources.get(candidate.source_id)
        if source is None:
            _candidate_issue(path, candidate, "source_id", "source_id does not exist", issues)

        if candidate.representation == "literal" and candidate.matcher != "exact":
            _candidate_issue(
                path, candidate, "matcher", "literal representation requires exact matcher", issues
            )
        if (
            candidate.representation == "literal"
            and candidate.normalized_canonical != candidate.normalized_surface
        ):
            _candidate_issue(
                path,
                candidate,
                "canonical",
                "literal canonical must match normalized surface",
                issues,
            )
        if candidate.representation == "alias" and candidate.matcher == "exact":
            _candidate_issue(
                path, candidate, "matcher", "alias representation requires alias matcher", issues
            )
        if (
            candidate.representation == "alias"
            and candidate.normalized_canonical not in all_literals
        ):
            _candidate_issue(
                path,
                candidate,
                "canonical",
                "alias canonical must resolve to literal candidate",
                issues,
            )

        if candidate.status == "packaged":
            if candidate.target_layer == "ai-candidate":
                _candidate_issue(
                    path, candidate, "target_layer", "ai-candidate must not be packaged", issues
                )
            if candidate.target_layer != "core":
                _candidate_issue(
                    path, candidate, "target_layer", "packaged candidate must target core", issues
                )
            if candidate.classification != "positive":
                _candidate_issue(
                    path,
                    candidate,
                    "classification",
                    "packaged candidate must be classified positive",
                    issues,
                )
            if (
                candidate.representation == "alias"
                and candidate.normalized_canonical not in packaged_literals
            ):
                _candidate_issue(
                    path,
                    candidate,
                    "canonical",
                    "alias canonical must resolve to packaged literal",
                    issues,
                )
            if candidate.review_status != "approved":
                _candidate_issue(
                    path,
                    candidate,
                    "review.status",
                    "packaged candidate must have approved review",
                    issues,
                )
            if not candidate.evaluation_refs:
                _candidate_issue(
                    path,
                    candidate,
                    "evaluation_refs",
                    "packaged candidate requires evaluation reference",
                    issues,
                )
            if source is not None and source.license_status != "approved":
                _candidate_issue(
                    path,
                    candidate,
                    "source_id",
                    "packaged candidate source license must be approved",
                    issues,
                )
            if source is not None and not source.redistribution_allowed:
                _candidate_issue(
                    path,
                    candidate,
                    "source_id",
                    "packaged candidate source must allow redistribution",
                    issues,
                )
            packaged_keys[
                (candidate.representation, candidate.normalized_surface, candidate.matcher)
            ] = candidate

        if candidate.classification == "hard-negative" and any(
            core_literal in candidate.normalized_surface
            for core_literal in registered_core_literals
        ):
            _candidate_issue(
                path,
                candidate,
                "classification",
                "hard-negative candidate contains registered core literal",
                issues,
            )

    for normalized_literal in required_literals:
        key = ("literal", normalized_literal, "exact")
        if key not in packaged_keys:
            issues.append(
                ProvenanceIssue(
                    path,
                    None,
                    "packaged.badwords",
                    "packaged literal has no approved provenance candidate",
                )
            )
    for alias, canonical, mode in aliases:
        key = ("alias", _normalize(alias), mode)
        alias_candidate = packaged_keys.get(key)
        if alias_candidate is None:
            issues.append(
                ProvenanceIssue(
                    path,
                    None,
                    "packaged.aliases",
                    "packaged alias has no approved provenance candidate",
                )
            )
        elif alias_candidate.normalized_canonical != _normalize(canonical):
            _candidate_issue(
                path,
                alias_candidate,
                "canonical",
                "packaged alias canonical differs from aliases.tsv",
                issues,
            )

    if len(packaged_literals) != len(required_literals):
        issues.append(
            ProvenanceIssue(
                path,
                None,
                "packaged.badwords",
                "packaged literal count differs from badwords file",
            )
        )
    packaged_alias_count = sum(
        candidate.status == "packaged" and candidate.representation == "alias"
        for candidate in candidates
    )
    if packaged_alias_count != len(aliases):
        issues.append(
            ProvenanceIssue(
                path,
                None,
                "packaged.aliases",
                "packaged alias count differs from aliases file",
            )
        )


def _candidate_issue(
    path: Path,
    candidate: _Candidate,
    field: str,
    message: str,
    issues: list[ProvenanceIssue],
) -> None:
    issues.append(ProvenanceIssue(path, candidate.candidate_id, field, message))


def _validate_fields(
    payload: dict[str, object],
    expected: frozenset[str],
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
) -> None:
    for name in sorted(expected - payload.keys()):
        issues.append(
            ProvenanceIssue(path, candidate_id, location, f"missing required field: {name}")
        )
    for name in sorted(payload.keys() - expected):
        issues.append(ProvenanceIssue(path, candidate_id, location, f"unknown field: {name}"))


def _identifier(
    payload: object,
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
) -> str | None:
    value = _text(payload, path, candidate_id, location, issues)
    if value is not None and _ID_PATTERN.fullmatch(value) is None:
        issues.append(
            ProvenanceIssue(path, candidate_id, location, "value is not a valid identifier")
        )
        return None
    return value


def _text(
    payload: object,
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
    *,
    allow_empty: bool = False,
) -> str | None:
    if not isinstance(payload, str) or (not allow_empty and not payload):
        issues.append(ProvenanceIssue(path, candidate_id, location, "value must be a string"))
        return None
    try:
        payload.encode("utf-8")
    except UnicodeEncodeError:
        issues.append(
            ProvenanceIssue(path, candidate_id, location, "value contains invalid Unicode")
        )
        return None
    return payload


def _nullable_text(
    payload: object,
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
) -> str | None:
    if payload is None:
        return None
    return _text(payload, path, candidate_id, location, issues)


def _enum(
    payload: object,
    allowed: frozenset[str],
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
) -> str | None:
    if not isinstance(payload, str) or payload not in allowed:
        issues.append(ProvenanceIssue(path, candidate_id, location, "unsupported enum value"))
        return None
    return payload


def _string_list(
    payload: object,
    path: Path,
    candidate_id: str | None,
    location: str,
    issues: list[ProvenanceIssue],
) -> tuple[str, ...] | None:
    if not isinstance(payload, list):
        issues.append(ProvenanceIssue(path, candidate_id, location, "value must be an array"))
        return None
    seen: set[str] = set()
    values: list[str] = []
    for index, value in enumerate(payload):
        if not isinstance(value, str) or not value:
            issues.append(
                ProvenanceIssue(
                    path, candidate_id, f"{location}[{index}]", "value must be a string"
                )
            )
        elif value in seen:
            issues.append(
                ProvenanceIssue(path, candidate_id, f"{location}[{index}]", "duplicate value")
            )
        else:
            seen.add(value)
            values.append(value)
    return tuple(values)


def _normalize(value: str) -> str:
    return normalize_text(value, "NFKC").text.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", nargs="?", type=Path, default=DICTIONARY_PROVENANCE_PATH)
    parser.add_argument("--badwords", type=Path, default=DEFAULT_BADWORDS_PATH)
    parser.add_argument("--aliases", type=Path, default=DEFAULT_ALIASES_PATH)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Validate provenance and print only aggregate promotion counts."""

    arguments = _parser().parse_args(argv)
    try:
        summary = validate_dictionary_provenance(
            arguments.manifest,
            badwords_path=arguments.badwords,
            aliases_path=arguments.aliases,
        )
    except DictionaryProvenanceError as exc:
        for issue in exc.issues:
            print(issue, file=sys.stderr)
        return 1
    print(
        f"validated {summary.candidate_count} candidates from {summary.source_count} sources; "
        f"packaged_literals={summary.packaged_literal_count}; "
        f"packaged_aliases={summary.packaged_alias_count}; "
        f"ai_candidates={summary.ai_candidate_count}; "
        f"pending_review={summary.pending_review_count}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
