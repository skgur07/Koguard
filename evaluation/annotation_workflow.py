"""Export blinded review batches and merge independent human annotations."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import (
    CORPUS_SCHEMA_PATH,
    CorpusValidationError,
    validate_corpus_paths,
)

ANNOTATION_BATCH_SCHEMA_PATH = Path(__file__).with_name("annotation-batch.schema.json")
ANNOTATION_REPORT_SCHEMA_PATH = Path(__file__).with_name("annotation-report.schema.json")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_BATCH_FIELDS = frozenset(
    {
        "schema_version",
        "annotation_set_id",
        "reviewer_id",
        "corpus_id",
        "corpus_sha256",
        "cases",
    }
)
_ANNOTATION_FIELDS = frozenset(
    {
        "case_id",
        "text",
        "privacy_status",
        "label",
        "expected_matches",
        "slices",
        "notes",
    }
)
_MATCH_FIELDS = frozenset({"start", "end", "canonical_term"})
_LABELS = frozenset({"positive", "hard-negative", "review"})
_PRIVACY_STATUSES = frozenset({"pending", "approved", "exclude"})
_MAX_BATCH_SIZE = 500


class AnnotationWorkflowError(ValueError):
    """Raised when a batch cannot be exported or safely merged."""


@dataclass(frozen=True, slots=True)
class AnnotationMergeResult:
    """Merged corpus and non-sensitive annotation quality report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _ValidatedBatch:
    annotation_set_id: str
    reviewer_id: str
    annotations: tuple[dict[str, Any], ...]


def export_annotation_batch(
    corpus_path: Path,
    *,
    annotation_set_id: str,
    reviewer_id: str,
    offset: int = 0,
    limit: int = 100,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Export a deterministic review-only batch without predictions or upstream labels."""

    _validate_output_paths((corpus_path,), output_path=output_path)
    annotation_set_id = _require_identifier(annotation_set_id, "annotation_set_id")
    reviewer_id = _require_identifier(reviewer_id, "reviewer_id")
    if type(offset) is not int or offset < 0:
        raise AnnotationWorkflowError("offset must be a non-negative integer")
    if type(limit) is not int or not 1 <= limit <= _MAX_BATCH_SIZE:
        raise AnnotationWorkflowError(f"limit must be between 1 and {_MAX_BATCH_SIZE}")

    corpus, corpus_sha256 = _load_corpus(corpus_path)
    cases = cast(list[dict[str, Any]], corpus["cases"])
    review_cases = sorted(
        (case for case in cases if case["label"] == "review"),
        key=lambda case: cast(str, case["id"]),
    )
    selected = review_cases[offset : offset + limit]
    if not selected:
        raise AnnotationWorkflowError("requested batch contains no review cases")

    batch: dict[str, Any] = {
        "schema_version": 1,
        "annotation_set_id": annotation_set_id,
        "reviewer_id": reviewer_id,
        "corpus_id": corpus["corpus_id"],
        "corpus_sha256": corpus_sha256,
        "cases": [
            {
                "case_id": case["id"],
                "text": case["text"],
                "privacy_status": "pending",
                "label": "review",
                "expected_matches": [],
                "slices": ["unadjudicated-intake"],
                "notes": "",
            }
            for case in selected
        ],
    }
    if output_path is not None:
        _write_json(output_path, batch)
    return batch


def merge_annotation_batches(
    corpus_path: Path,
    primary_path: Path,
    secondary_path: Path,
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> AnnotationMergeResult:
    """Promote only privacy-approved agreement from two independent annotation batches."""

    _validate_output_paths(
        (corpus_path, primary_path, secondary_path),
        output_path=output_path,
        report_path=report_path,
    )
    corpus, corpus_sha256 = _load_corpus(corpus_path)
    corpus_id = cast(str, corpus["corpus_id"])
    cases = cast(list[dict[str, Any]], corpus["cases"])
    source_by_id = {cast(str, case["id"]): case for case in cases}
    primary = _load_and_validate_batch(
        primary_path,
        corpus_id=corpus_id,
        corpus_sha256=corpus_sha256,
        source_by_id=source_by_id,
    )
    secondary = _load_and_validate_batch(
        secondary_path,
        corpus_id=corpus_id,
        corpus_sha256=corpus_sha256,
        source_by_id=source_by_id,
    )
    if primary.annotation_set_id == secondary.annotation_set_id:
        raise AnnotationWorkflowError("annotation set IDs must differ")
    if primary.reviewer_id == secondary.reviewer_id:
        raise AnnotationWorkflowError("reviewer IDs must differ")

    primary_by_id = {
        cast(str, annotation["case_id"]): annotation for annotation in primary.annotations
    }
    secondary_by_id = {
        cast(str, annotation["case_id"]): annotation for annotation in secondary.annotations
    }
    if set(primary_by_id) != set(secondary_by_id):
        raise AnnotationWorkflowError("annotation batches must contain the same case IDs")

    merged = copy.deepcopy(corpus)
    merged_cases = cast(list[dict[str, Any]], merged["cases"])
    merged_by_id = {cast(str, case["id"]): case for case in merged_cases}
    batch_counts: Counter[str] = Counter()
    slice_counts: Counter[str] = Counter()
    quality_counts: Counter[str] = Counter()

    for case_id in sorted(primary_by_id):
        first = primary_by_id[case_id]
        second = secondary_by_id[case_id]
        target = merged_by_id[case_id]
        first_privacy = cast(str, first["privacy_status"])
        second_privacy = cast(str, second["privacy_status"])

        if "exclude" in {first_privacy, second_privacy}:
            quality_counts["privacy_excluded"] += 1
            _retain_review(target, "Privacy review excluded this case from gold.")
        elif "pending" in {first_privacy, second_privacy}:
            quality_counts["pending_privacy"] += 1
            _retain_review(target, "Privacy review is still pending.")
        else:
            quality_counts["double_reviewed"] += 1
            if _decision_key(first) != _decision_key(second):
                quality_counts["disagreement"] += 1
                _retain_review(
                    target, "Independent annotation disagreement; adjudication required."
                )
            else:
                quality_counts["consensus"] += 1
                _apply_consensus(target, first, second)

        label = cast(str, target["label"])
        batch_counts[label] += 1
        if label != "review":
            slice_counts.update(cast(list[str], target["slices"]))

    corpus_counts = Counter(cast(str, case["label"]) for case in merged_cases)
    report: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": corpus_id,
        "source_corpus_sha256": corpus_sha256,
        "batch_case_count": len(primary_by_id),
        "batch_counts": _label_counts(batch_counts),
        "corpus_counts": _label_counts(corpus_counts),
        "quality_counts": {
            name: quality_counts[name]
            for name in (
                "double_reviewed",
                "consensus",
                "disagreement",
                "privacy_excluded",
                "pending_privacy",
            )
        },
        "slice_counts": dict(sorted(slice_counts.items())),
        "gold_ready": False,
    }
    result = AnnotationMergeResult(merged, report)
    if output_path is not None:
        _write_json(output_path, merged)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _load_corpus(path: Path) -> tuple[dict[str, Any], str]:
    try:
        validate_corpus_paths([path])
    except CorpusValidationError as exc:
        raise AnnotationWorkflowError("input corpus violates the corpus contract") from exc
    corpus = _read_object(path, "corpus")
    try:
        corpus_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise AnnotationWorkflowError("failed to read corpus bytes") from exc
    return corpus, corpus_sha256


def _load_allowed_slices() -> frozenset[str]:
    try:
        payload: object = json.loads(CORPUS_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("failed to read the corpus schema") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("corpus schema root must be an object")
    schema = cast(dict[str, Any], payload)
    try:
        definitions = cast(dict[str, Any], schema["$defs"])
        case_schema = cast(dict[str, Any], definitions["case"])
        properties = cast(dict[str, Any], case_schema["properties"])
        slices = cast(dict[str, Any], properties["slices"])
        items = cast(dict[str, Any], slices["items"])
        values = items["enum"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError("corpus schema is missing the slice enum") from exc
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise RuntimeError("corpus schema slice enum is invalid")
    return frozenset(cast(list[str], values))


_ALLOWED_SLICES = _load_allowed_slices()


def _load_and_validate_batch(
    path: Path,
    *,
    corpus_id: str,
    corpus_sha256: str,
    source_by_id: Mapping[str, dict[str, Any]],
) -> _ValidatedBatch:
    batch = _read_object(path, "annotation batch")
    if set(batch) != _BATCH_FIELDS or batch.get("schema_version") != 1:
        raise AnnotationWorkflowError("annotation batch violates version 1 contract")
    annotation_set_id = _require_identifier(batch.get("annotation_set_id"), "annotation_set_id")
    reviewer_id = _require_identifier(batch.get("reviewer_id"), "reviewer_id")
    if batch.get("corpus_id") != corpus_id:
        raise AnnotationWorkflowError("annotation batch corpus_id mismatch")
    batch_hash = batch.get("corpus_sha256")
    if not isinstance(batch_hash, str) or _SHA256_PATTERN.fullmatch(batch_hash) is None:
        raise AnnotationWorkflowError("annotation batch corpus_sha256 is invalid")
    if batch_hash != corpus_sha256:
        raise AnnotationWorkflowError("annotation batch corpus SHA-256 mismatch")

    raw_annotations = batch.get("cases")
    if (
        not isinstance(raw_annotations, list)
        or not raw_annotations
        or len(raw_annotations) > _MAX_BATCH_SIZE
    ):
        raise AnnotationWorkflowError("annotation batch cases must contain 1 to 500 items")
    annotations: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, raw_annotation in enumerate(raw_annotations):
        annotation = _validate_annotation(
            raw_annotation,
            index=index,
            source_by_id=source_by_id,
        )
        case_id = cast(str, annotation["case_id"])
        if case_id in seen_ids:
            raise AnnotationWorkflowError(f"duplicate annotation case ID {case_id!r}")
        seen_ids.add(case_id)
        annotations.append(annotation)
    return _ValidatedBatch(annotation_set_id, reviewer_id, tuple(annotations))


def _validate_annotation(
    payload: object,
    *,
    index: int,
    source_by_id: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    location = f"cases[{index}]"
    if not isinstance(payload, dict) or set(payload) != _ANNOTATION_FIELDS:
        raise AnnotationWorkflowError(f"{location} violates the annotation contract")
    annotation = cast(dict[str, Any], payload)
    case_id = _require_identifier(annotation.get("case_id"), f"{location}.case_id")
    source_case = source_by_id.get(case_id)
    if source_case is None:
        raise AnnotationWorkflowError(f"{location} references an unknown case ID")
    if source_case["label"] != "review":
        raise AnnotationWorkflowError(f"{location} must reference a review case")
    text = annotation.get("text")
    if not isinstance(text, str) or len(text) > 4096 or not _is_valid_utf8(text):
        raise AnnotationWorkflowError(f"{location}.text is invalid")
    if text != source_case["text"]:
        raise AnnotationWorkflowError(f"{location} source text mismatch for case {case_id!r}")

    privacy_status = annotation.get("privacy_status")
    if not isinstance(privacy_status, str) or privacy_status not in _PRIVACY_STATUSES:
        raise AnnotationWorkflowError(f"{location}.privacy_status is invalid")
    label = annotation.get("label")
    if not isinstance(label, str) or label not in _LABELS:
        raise AnnotationWorkflowError(f"{location}.label is invalid")
    notes = annotation.get("notes")
    if not isinstance(notes, str) or len(notes) > 500 or not _is_valid_utf8(notes):
        raise AnnotationWorkflowError(f"{location}.notes is invalid")
    matches = _validate_matches(annotation.get("expected_matches"), text, location)
    slices = _validate_slices(annotation.get("slices"), location)

    if label == "positive" and not matches:
        raise AnnotationWorkflowError(f"{location} positive annotation requires a match")
    if label != "positive" and matches:
        raise AnnotationWorkflowError(
            f"{location} non-positive annotation must not contain matches"
        )
    if privacy_status != "approved":
        if label != "review" or matches or slices != ["unadjudicated-intake"]:
            raise AnnotationWorkflowError(
                f"{location} non-approved annotation must remain unadjudicated review"
            )
    elif label == "review":
        if slices != ["unadjudicated-intake"]:
            raise AnnotationWorkflowError(f"{location} approved review must remain unadjudicated")
    else:
        if "unadjudicated-intake" in slices:
            raise AnnotationWorkflowError(
                f"{location} finalized annotation must use real evaluation slices"
            )
        if not notes:
            raise AnnotationWorkflowError(f"{location} finalized annotation requires notes")
    return annotation


def _validate_matches(payload: object, text: str, location: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise AnnotationWorkflowError(f"{location}.expected_matches must be an array")
    matches: list[dict[str, Any]] = []
    previous_end = -1
    for index, raw_match in enumerate(payload):
        match_location = f"{location}.expected_matches[{index}]"
        if not isinstance(raw_match, dict) or set(raw_match) != _MATCH_FIELDS:
            raise AnnotationWorkflowError(f"{match_location} violates the match contract")
        start = raw_match.get("start")
        end = raw_match.get("end")
        canonical_term = raw_match.get("canonical_term")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text):
            raise AnnotationWorkflowError(f"{match_location} span is invalid")
        if start < previous_end:
            raise AnnotationWorkflowError(
                f"{location}.expected_matches must be sorted and disjoint"
            )
        if (
            not isinstance(canonical_term, str)
            or not 1 <= len(canonical_term) <= 128
            or not _is_valid_utf8(canonical_term)
        ):
            raise AnnotationWorkflowError(f"{match_location}.canonical_term is invalid")
        previous_end = end
        matches.append(cast(dict[str, Any], raw_match))
    return matches


def _validate_slices(payload: object, location: str) -> list[str]:
    if not isinstance(payload, list) or not payload:
        raise AnnotationWorkflowError(f"{location}.slices must be a non-empty array")
    if any(not isinstance(value, str) or value not in _ALLOWED_SLICES for value in payload):
        raise AnnotationWorkflowError(f"{location}.slices contains an unsupported value")
    slices = cast(list[str], payload)
    if len(set(slices)) != len(slices):
        raise AnnotationWorkflowError(f"{location}.slices must not contain duplicates")
    return slices


def _decision_key(annotation: Mapping[str, Any]) -> tuple[object, ...]:
    matches = cast(list[dict[str, Any]], annotation["expected_matches"])
    return (
        annotation["label"],
        tuple((match["start"], match["end"], match["canonical_term"]) for match in matches),
        tuple(sorted(cast(list[str], annotation["slices"]))),
    )


def _apply_consensus(
    target: dict[str, Any],
    primary: Mapping[str, Any],
    secondary: Mapping[str, Any],
) -> None:
    target["label"] = primary["label"]
    target["expected_matches"] = copy.deepcopy(primary["expected_matches"])
    target["slices"] = sorted(cast(list[str], primary["slices"]))
    primary_notes = cast(str, primary["notes"])
    secondary_notes = cast(str, secondary["notes"])
    if primary["label"] == "review":
        target["notes"] = "Double review retained review status; adjudication may still be needed."
    else:
        target["notes"] = (
            f"Double-reviewed consensus. Primary: {primary_notes} Secondary: {secondary_notes}"
        )


def _retain_review(target: dict[str, Any], notes: str) -> None:
    target["label"] = "review"
    target["expected_matches"] = []
    target["slices"] = ["unadjudicated-intake"]
    target["notes"] = notes


def _label_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {label: counts.get(label, 0) for label in ("positive", "hard-negative", "review")}


def _validate_output_paths(
    input_paths: Sequence[Path],
    *,
    output_path: Path | None,
    report_path: Path | None = None,
) -> None:
    resolved_inputs = {path.resolve() for path in input_paths}
    if output_path is not None and output_path.resolve() in resolved_inputs:
        raise AnnotationWorkflowError("output must not overwrite an input")
    if report_path is not None and report_path.resolve() in resolved_inputs:
        raise AnnotationWorkflowError("output must not overwrite an input")
    if (
        output_path is not None
        and report_path is not None
        and output_path.resolve() == report_path.resolve()
    ):
        raise AnnotationWorkflowError("output and report paths must differ")


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise AnnotationWorkflowError(f"{name} is invalid")
    return value


def _is_valid_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AnnotationWorkflowError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise AnnotationWorkflowError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as exc:
        raise AnnotationWorkflowError("failed to write JSON output") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser("export", help="export a blinded review batch")
    export_parser.add_argument("corpus", type=Path)
    export_parser.add_argument("--annotation-set-id", required=True)
    export_parser.add_argument("--reviewer-id", required=True)
    export_parser.add_argument("--offset", type=int, default=0)
    export_parser.add_argument("--limit", type=int, default=100)
    export_parser.add_argument("--output", required=True, type=Path)

    merge_parser = subparsers.add_parser("merge", help="merge two independent annotations")
    merge_parser.add_argument("corpus", type=Path)
    merge_parser.add_argument("primary", type=Path)
    merge_parser.add_argument("secondary", type=Path)
    merge_parser.add_argument("--output", required=True, type=Path)
    merge_parser.add_argument("--report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run annotation export or merge without printing corpus content."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "export":
            batch = export_annotation_batch(
                arguments.corpus,
                annotation_set_id=arguments.annotation_set_id,
                reviewer_id=arguments.reviewer_id,
                offset=arguments.offset,
                limit=arguments.limit,
                output_path=arguments.output,
            )
            print(
                f"corpus={batch['corpus_id']}; exported={len(batch['cases'])}; "
                f"offset={arguments.offset}"
            )
        else:
            result = merge_annotation_batches(
                arguments.corpus,
                arguments.primary,
                arguments.secondary,
                output_path=arguments.output,
                report_path=arguments.report,
            )
            counts = cast(dict[str, int], result.report["batch_counts"])
            quality = cast(dict[str, int], result.report["quality_counts"])
            print(
                f"batch={result.report['batch_case_count']}; positive={counts['positive']}; "
                f"hard-negative={counts['hard-negative']}; review={counts['review']}; "
                f"disagreement={quality['disagreement']}"
            )
    except AnnotationWorkflowError as exc:
        print(f"annotation workflow failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
