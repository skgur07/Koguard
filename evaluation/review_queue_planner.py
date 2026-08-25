"""Build deterministic source-balanced queues from protected review corpora."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_MAX_BATCH_SIZE = 500


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
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> ReviewQueueResult:
    """Select a deterministic round-robin queue without using labels or predictions."""

    _validate_output_paths(corpus_path, output_path, report_path)
    queue_id = _require_identifier(queue_id, "queue_id")
    corpus_id = _require_identifier(corpus_id, "corpus_id")
    if type(limit) is not int or not 1 <= limit <= _MAX_BATCH_SIZE:
        raise ReviewQueueError(f"limit must be between 1 and {_MAX_BATCH_SIZE}")
    source = _load_corpus(corpus_path)
    review_cases = [
        case for case in cast(list[dict[str, Any]], source["cases"]) if case["label"] == "review"
    ]
    if not review_cases:
        raise ReviewQueueError("source corpus contains no review cases")

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_details: dict[str, dict[str, Any]] = {}
    for case in review_cases:
        source_data = cast(dict[str, Any], case["source"])
        source_key = _canonical_sha256(source_data)
        grouped[source_key].append(case)
        source_details[source_key] = source_data
    for cases in grouped.values():
        cases.sort(
            key=lambda case: (
                hashlib.sha256(f"{queue_id}\0{cast(str, case['id'])}".encode()).hexdigest(),
                cast(str, case["id"]),
            )
        )

    selected: list[dict[str, Any]] = []
    selected_by_source: dict[str, int] = defaultdict(int)
    source_keys = sorted(grouped)
    while len(selected) < min(limit, len(review_cases)):
        advanced = False
        for source_key in source_keys:
            index = selected_by_source[source_key]
            cases = grouped[source_key]
            if index >= len(cases):
                continue
            selected.append(copy.deepcopy(cases[index]))
            selected_by_source[source_key] += 1
            advanced = True
            if len(selected) == min(limit, len(review_cases)):
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
        "selection": "source-round-robin-sha256-v1",
        "available_review_count": len(review_cases),
        "selected_count": len(selected),
        "source_statistics": statistics,
        "uses_detector_predictions": False,
        "uses_upstream_labels": False,
        "gold_ready": False,
    }
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


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ReviewQueueError(f"{name} is invalid")
    return value


def _validate_output_paths(
    input_path: Path, output_path: Path | None, report_path: Path | None
) -> None:
    resolved_input = input_path.resolve()
    outputs = [path.resolve() for path in (output_path, report_path) if path is not None]
    if resolved_input in outputs or len(set(outputs)) != len(outputs):
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
            output_path=arguments.output,
            report_path=arguments.report,
        )
    except ReviewQueueError as exc:
        print(f"review queue planning failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"available={result.report['available_review_count']}; "
        f"selected={result.report['selected_count']}; gold_ready=false"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
