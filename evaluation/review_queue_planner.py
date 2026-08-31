"""Build deterministic source-balanced queues from protected review corpora."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_MAX_BATCH_SIZE = 500
_ANNOTATION_BATCH_FIELDS = {
    "schema_version",
    "annotation_set_id",
    "reviewer_id",
    "corpus_id",
    "corpus_sha256",
    "cases",
}
_ANNOTATION_FIELDS = {
    "case_id",
    "text",
    "privacy_status",
    "label",
    "expected_matches",
    "slices",
    "notes",
}
_SURFACE_SIGNAL_PATTERNS = {
    "modern-jamo": re.compile(r"[\u1100-\u11ff]"),
    "ascii-token": re.compile(r"[A-Za-z]{3,}"),
    "single-hangul-gap": re.compile(r"(?<![가-힣])[가-힣] {1,3}[가-힣](?![가-힣])"),
    "hangul-separator": re.compile(r"[가-힣][!#$%&*+,.=@^_~·-]+[가-힣]"),
    "choseong-run": re.compile(r"[ㄱ-ㅎ]{2,}"),
    "repeated-character": re.compile(r"(.)\1{2,}"),
    "quoted-marker": re.compile(r"[\"'“”‘’「」『』]"),
    "username-marker": re.compile(r"[@#][^\s]{2,}"),
    "non-bmp-unicode": re.compile(r"[\U00010000-\U0010ffff]"),
    "compat-jamo": re.compile(r"[ㄱ-ㅎㅏ-ㅣ]"),
}
_SURFACE_SIGNAL_WEIGHTS = {
    "modern-jamo": 100,
    "ascii-token": 90,
    "single-hangul-gap": 80,
    "hangul-separator": 70,
    "choseong-run": 60,
    "repeated-character": 50,
    "quoted-marker": 40,
    "username-marker": 35,
    "non-bmp-unicode": 30,
    "compat-jamo": 20,
}


class ReviewQueueError(ValueError):
    """Raised when a source-balanced review queue cannot be prepared safely."""


@dataclass(frozen=True, slots=True)
class ReviewQueueResult:
    """A protected review-only corpus and aggregate-only selection report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


def prepare_review_queue(
    corpus_path: Path,
    *,
    queue_id: str,
    corpus_id: str,
    limit: int = 500,
    surface_priority: bool = False,
    exclude_corpus_paths: Sequence[Path] = (),
    exclude_annotation_batch_paths: Sequence[Path] = (),
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> ReviewQueueResult:
    """Select a deterministic round-robin queue without using labels or predictions."""

    _validate_output_paths(
        corpus_path,
        (*exclude_corpus_paths, *exclude_annotation_batch_paths),
        output_path,
        report_path,
    )
    queue_id = _require_identifier(queue_id, "queue_id")
    corpus_id = _require_identifier(corpus_id, "corpus_id")
    if type(limit) is not int or not 1 <= limit <= _MAX_BATCH_SIZE:
        raise ReviewQueueError(f"limit must be between 1 and {_MAX_BATCH_SIZE}")
    source = _load_corpus(corpus_path)
    source_cases = cast(list[dict[str, Any]], source["cases"])
    source_by_id = {cast(str, case["id"]): case for case in source_cases}
    excluded_corpus_ids = _load_excluded_case_ids(exclude_corpus_paths, source_by_id)
    excluded_annotation_ids = _load_annotation_excluded_case_ids(
        exclude_annotation_batch_paths,
        source_corpus_id=cast(str, source["corpus_id"]),
        source_by_id=source_by_id,
    )
    exclusion_input_overlap_count = len(excluded_corpus_ids & excluded_annotation_ids)
    excluded_ids = excluded_corpus_ids | excluded_annotation_ids
    review_cases = [case for case in source_cases if case["label"] == "review"]
    if not review_cases:
        raise ReviewQueueError("source corpus contains no review cases")
    excluded_review_case_count = len(
        {cast(str, case["id"]) for case in review_cases} & excluded_ids
    )
    eligible_cases = [case for case in review_cases if case["id"] not in excluded_ids]
    if not eligible_cases:
        raise ReviewQueueError("no eligible review cases remain after exclusions")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_details: dict[str, dict[str, Any]] = {}
    for case in eligible_cases:
        source_data = cast(dict[str, Any], case["source"])
        source_key = _canonical_sha256(source_data)
        grouped[source_key].append(case)
        source_details[source_key] = source_data
    signal_cache = {
        cast(str, case["id"]): _surface_signals(cast(str, case["text"])) for case in eligible_cases
    }
    for cases in grouped.values():
        cases.sort(
            key=lambda case: (
                (
                    -_surface_priority_score(signal_cache[cast(str, case["id"])]),
                    -len(signal_cache[cast(str, case["id"])]),
                    hashlib.sha256(f"{queue_id}\0{cast(str, case['id'])}".encode()).hexdigest(),
                    cast(str, case["id"]),
                )
                if surface_priority
                else (
                    hashlib.sha256(f"{queue_id}\0{cast(str, case['id'])}".encode()).hexdigest(),
                    cast(str, case["id"]),
                )
            )
        )

    selected: list[dict[str, Any]] = []
    selected_by_source: dict[str, int] = defaultdict(int)
    source_keys = sorted(grouped)
    while len(selected) < min(limit, len(eligible_cases)):
        advanced = False
        for source_key in source_keys:
            index = selected_by_source[source_key]
            cases = grouped[source_key]
            if index >= len(cases):
                continue
            selected.append(copy.deepcopy(cases[index]))
            selected_by_source[source_key] += 1
            advanced = True
            if len(selected) == min(limit, len(eligible_cases)):
                break
        if not advanced:
            break

    selected.sort(key=lambda case: cast(str, case["id"]))
    corpus = {"schema_version": 1, "corpus_id": corpus_id, "cases": selected}
    statistics = [
        {
            "source_fingerprint": source_key,
            "source_name": cast(str, source_details[source_key]["name"]),
            "available_count": len(grouped[source_key]),
            "selected_count": selected_by_source[source_key],
        }
        for source_key in source_keys
    ]
    report = {
        "schema_version": 1,
        "queue_id": queue_id,
        "selection": (
            "surface-signal-source-round-robin-sha256-v1"
            if surface_priority
            else "source-round-robin-sha256-v1"
        ),
        "available_review_count": len(review_cases),
        "excluded_case_count": len(excluded_ids),
        "excluded_corpus_case_count": len(excluded_corpus_ids),
        "excluded_annotation_case_count": len(excluded_annotation_ids),
        "excluded_input_overlap_count": exclusion_input_overlap_count,
        "excluded_review_case_count": excluded_review_case_count,
        "eligible_review_count": len(eligible_cases),
        "selected_count": len(selected),
        "selected_existing_overlap_count": len(
            {cast(str, case["id"]) for case in selected} & excluded_ids
        ),
        "source_statistics": statistics,
        "uses_detector_predictions": False,
        "uses_upstream_labels": False,
        "gold_ready": False,
    }
    if surface_priority:
        candidate_signal_counts = Counter(
            signal for signals in signal_cache.values() for signal in signals
        )
        selected_signals = [signal_cache[cast(str, case["id"])] for case in selected]
        selected_signal_counts = Counter(
            signal for signals in selected_signals for signal in signals
        )
        report.update(
            {
                "surface_signal_candidate_counts": dict(sorted(candidate_signal_counts.items())),
                "surface_signal_selected_counts": dict(sorted(selected_signal_counts.items())),
                "selected_with_surface_signal_count": sum(
                    bool(signals) for signals in selected_signals
                ),
            }
        )
    result = ReviewQueueResult(corpus, report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _load_corpus(path: Path) -> dict[str, Any]:
    try:
        validate_corpus_paths([path])
    except CorpusValidationError as exc:
        raise ReviewQueueError("source corpus violates the corpus contract") from exc
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewQueueError("failed to read source corpus") from exc
    if not isinstance(payload, dict):
        raise ReviewQueueError("source corpus root must be an object")
    return cast(dict[str, Any], payload)


def _load_excluded_case_ids(
    paths: Sequence[Path],
    source_by_id: Mapping[str, dict[str, Any]],
) -> set[str]:
    excluded_ids: set[str] = set()
    for path in paths:
        excluded = _load_corpus(path)
        for case in cast(list[dict[str, Any]], excluded["cases"]):
            case_id = cast(str, case["id"])
            source_case = source_by_id.get(case_id)
            if source_case is None or not _same_case_identity(source_case, case):
                raise ReviewQueueError("exclusion corpus does not match source corpus")
            if case_id in excluded_ids:
                raise ReviewQueueError("exclusion corpora contain overlapping cases")
            excluded_ids.add(case_id)
    return excluded_ids


def _same_case_identity(source: Mapping[str, Any], excluded: Mapping[str, Any]) -> bool:
    identity_fields = ("id", "text", "source", "license", "split")
    return all(source.get(field) == excluded.get(field) for field in identity_fields)


def _load_annotation_excluded_case_ids(
    paths: Sequence[Path],
    *,
    source_corpus_id: str,
    source_by_id: Mapping[str, dict[str, Any]],
) -> set[str]:
    excluded_ids: set[str] = set()
    for path in paths:
        batch = _read_object(path, "annotation exclusion")
        cases = batch.get("cases")
        if (
            set(batch) != _ANNOTATION_BATCH_FIELDS
            or batch.get("schema_version") != 1
            or batch.get("corpus_id") != source_corpus_id
            or _ID_PATTERN.fullmatch(str(batch.get("annotation_set_id"))) is None
            or _ID_PATTERN.fullmatch(str(batch.get("reviewer_id"))) is None
            or _SHA256_PATTERN.fullmatch(str(batch.get("corpus_sha256"))) is None
            or not isinstance(cases, list)
            or not 1 <= len(cases) <= _MAX_BATCH_SIZE
        ):
            raise ReviewQueueError("annotation exclusion does not match source corpus")
        for annotation in cases:
            if not isinstance(annotation, dict) or set(annotation) != _ANNOTATION_FIELDS:
                raise ReviewQueueError("annotation exclusion does not match source corpus")
            case_id = annotation.get("case_id")
            text = annotation.get("text")
            source_case = source_by_id.get(case_id) if isinstance(case_id, str) else None
            if source_case is None or text != source_case["text"] or case_id in excluded_ids:
                raise ReviewQueueError("annotation exclusion does not match source corpus")
            excluded_ids.add(cast(str, case_id))
    return excluded_ids


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _surface_signals(text: str) -> tuple[str, ...]:
    return tuple(
        name
        for name, pattern in _SURFACE_SIGNAL_PATTERNS.items()
        if pattern.search(text) is not None
    )


def _surface_priority_score(signals: Sequence[str]) -> int:
    return sum(_SURFACE_SIGNAL_WEIGHTS[signal] for signal in signals)


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewQueueError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise ReviewQueueError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ReviewQueueError(f"{name} is invalid")
    return value


def _validate_output_paths(
    input_path: Path,
    exclude_corpus_paths: Sequence[Path],
    output_path: Path | None,
    report_path: Path | None,
) -> None:
    inputs = {input_path.resolve(), *(path.resolve() for path in exclude_corpus_paths)}
    outputs = [path.resolve() for path in (output_path, report_path) if path is not None]
    if any(path in inputs for path in outputs) or len(set(outputs)) != len(outputs):
        raise ReviewQueueError("queue outputs must not overwrite inputs or each other")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReviewQueueError("failed to write queue output") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--queue-id", required=True)
    parser.add_argument("--corpus-id", required=True)
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument(
        "--surface-priority",
        action="store_true",
        help="rank detector-blind text-shape signals before the per-source stable hash",
    )
    parser.add_argument(
        "--exclude-corpus",
        action="append",
        default=[],
        type=Path,
        help="previous protected queue to exclude; repeat for multiple queues",
    )
    parser.add_argument(
        "--exclude-annotation-batch",
        action="append",
        default=[],
        type=Path,
        help="previous protected annotation batch to exclude; repeat for multiple batches",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write a protected queue and print aggregate counts only."""

    arguments = _parser().parse_args(argv)
    try:
        result = prepare_review_queue(
            arguments.corpus,
            queue_id=arguments.queue_id,
            corpus_id=arguments.corpus_id,
            limit=arguments.limit,
            surface_priority=arguments.surface_priority,
            exclude_corpus_paths=arguments.exclude_corpus,
            exclude_annotation_batch_paths=arguments.exclude_annotation_batch,
            output_path=arguments.output,
            report_path=arguments.report,
        )
    except ReviewQueueError as exc:
        print(f"review queue planning failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"available={result.report['available_review_count']}; "
        f"excluded={result.report['excluded_case_count']}; "
        f"eligible={result.report['eligible_review_count']}; "
        f"selected={result.report['selected_count']}; gold_ready=false"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
