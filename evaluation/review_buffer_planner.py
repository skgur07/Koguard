"""Build a deterministic source-balanced review buffer beyond existing intakes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths

BUFFER_CONFIG_SCHEMA_PATH = Path(__file__).with_name("review-buffer.schema.json")
BUFFER_REPORT_SCHEMA_PATH = Path(__file__).with_name("review-buffer-report.schema.json")
_CONFIG_FIELDS = frozenset(
    {
        "schema_version",
        "buffer_id",
        "corpus_id",
        "split",
        "selection",
        "max_source_share",
        "selection_uses_upstream_labels_for_targeting",
        "sources",
    }
)
_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "corpus_path",
        "expected_corpus_id",
        "existing_corpus_path",
        "expected_existing_corpus_id",
        "quota",
    }
)


class ReviewBufferError(ValueError):
    """Raised when a disjoint review buffer cannot be built safely."""


@dataclass(frozen=True, slots=True)
class ReviewBufferResult:
    """A protected review corpus and aggregate-only planning report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _SourceConfig:
    source_id: str
    corpus_path: Path
    expected_corpus_id: str
    existing_corpus_path: Path
    expected_existing_corpus_id: str
    quota: int


def build_review_buffer(
    config_path: Path,
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> ReviewBufferResult:
    """Select only cases outside each source's already admitted intake."""

    config, sources = _load_config(config_path)
    _validate_output_paths(config_path, sources, output_path, report_path)
    buffer_id = cast(str, config["buffer_id"])
    selected: list[dict[str, Any]] = []
    selected_direct: set[bytes] = set()
    selected_normalized: set[bytes] = set()
    all_existing_direct: set[bytes] = set()
    all_existing_normalized: set[bytes] = set()
    statistics: list[dict[str, Any]] = []
    loaded_sources: list[tuple[_SourceConfig, list[dict[str, Any]]]] = []

    for source in sources:
        candidates = _load_review_corpus(source.corpus_path, source.expected_corpus_id)
        existing = _load_review_corpus(
            source.existing_corpus_path,
            source.expected_existing_corpus_id,
        )
        all_existing_direct.update(_text_hash(cast(str, case["text"])) for case in existing)
        all_existing_normalized.update(
            _normalized_text_hash(cast(str, case["text"])) for case in existing
        )
        loaded_sources.append((source, candidates))

    selected_opaque_ids: set[str] = set()
    for source, candidates in loaded_sources:
        local_direct: set[bytes] = set()
        local_normalized: set[bytes] = set()
        eligible: list[tuple[dict[str, Any], bytes, bytes]] = []
        existing_excluded_count = 0
        duplicate_excluded_count = 0
        ranked = sorted(
            candidates,
            key=lambda case: (
                hashlib.sha256(
                    f"{buffer_id}\0select\0{cast(str, case['id'])}".encode()
                ).hexdigest(),
                cast(str, case["id"]),
            ),
        )
        for case in ranked:
            text = cast(str, case["text"])
            direct = _text_hash(text)
            normalized = _normalized_text_hash(text)
            if direct in all_existing_direct or normalized in all_existing_normalized:
                existing_excluded_count += 1
                continue
            if (
                direct in local_direct
                or normalized in local_normalized
                or direct in selected_direct
                or normalized in selected_normalized
            ):
                duplicate_excluded_count += 1
                continue
            local_direct.add(direct)
            local_normalized.add(normalized)
            eligible.append((case, direct, normalized))
        if len(eligible) < source.quota:
            raise ReviewBufferError(
                f"source {source.source_id!r} has insufficient incremental review cases"
            )
        for case, direct, normalized in eligible[: source.quota]:
            copied = copy.deepcopy(case)
            original_id = cast(str, copied["id"])
            opaque_id = (
                "buffer-"
                + hashlib.sha256(
                    f"{buffer_id}\0opaque\0{source.source_id}\0{original_id}".encode()
                ).hexdigest()[:24]
            )
            if opaque_id in selected_opaque_ids:
                raise ReviewBufferError("opaque buffer ID collision")
            selected_opaque_ids.add(opaque_id)
            copied["id"] = opaque_id
            selected.append(copied)
            selected_direct.add(direct)
            selected_normalized.add(normalized)
        statistics.append(
            {
                "source_id": source.source_id,
                "available_count": len(candidates),
                "existing_excluded_count": existing_excluded_count,
                "duplicate_excluded_count": duplicate_excluded_count,
                "eligible_count": len(eligible),
                "selected_count": source.quota,
                "share": 0.0,
            }
        )

    selected.sort(key=lambda case: cast(str, case["id"]))
    total = len(selected)
    if total < 1:
        raise ReviewBufferError("buffer selected no cases")
    for row in statistics:
        row["share"] = cast(int, row["selected_count"]) / total
    maximum_share = max(cast(float, row["share"]) for row in statistics)
    configured_maximum = cast(float, config["max_source_share"])
    if maximum_share > configured_maximum + 1e-12:
        raise ReviewBufferError("source share exceeds the configured maximum")
    overlap_count = sum(
        1
        for case in selected
        if _text_hash(cast(str, case["text"])) in all_existing_direct
        or _normalized_text_hash(cast(str, case["text"])) in all_existing_normalized
    )
    if overlap_count:
        raise ReviewBufferError("selected buffer overlaps an existing intake")

    corpus = {
        "schema_version": 1,
        "corpus_id": config["corpus_id"],
        "cases": selected,
    }
    report = {
        "schema_version": 1,
        "buffer_id": buffer_id,
        "corpus_id": config["corpus_id"],
        "selection": config["selection"],
        "selected_count": total,
        "configured_max_source_share": configured_maximum,
        "maximum_observed_source_share": maximum_share,
        "source_bias_gate_passed": True,
        "source_statistics": statistics,
        "selection_uses_upstream_labels_for_targeting": True,
        "upstream_labels_are_gold": False,
        "generated_label_counts": {
            "positive": 0,
            "hard-negative": 0,
            "review": total,
        },
        "selected_existing_overlap_count": overlap_count,
        "gold_ready": False,
        "completion_blockers": [
            "Every selected case still requires independent double annotation.",
            "Upstream labels are targeting hints and must not become Koguard gold.",
            "Disagreements require an independent third reviewer.",
            "Independent hidden evaluation is not part of this tuning buffer.",
        ],
    }
    result = ReviewBufferResult(corpus, report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _load_config(path: Path) -> tuple[dict[str, Any], tuple[_SourceConfig, ...]]:
    payload = _read_object(path, "buffer configuration")
    if set(payload) != _CONFIG_FIELDS or payload.get("schema_version") != 1:
        raise ReviewBufferError("buffer configuration violates version 1 contract")
    for name in ("buffer_id", "corpus_id"):
        value = payload.get(name)
        if not isinstance(value, str) or not value or len(value) > 128:
            raise ReviewBufferError(f"{name} is invalid")
    if (
        payload.get("split") != "tuning"
        or payload.get("selection") != "incremental-source-sha256-v1"
        or payload.get("selection_uses_upstream_labels_for_targeting") is not True
    ):
        raise ReviewBufferError("buffer selection policy is unsupported")
    maximum = payload.get("max_source_share")
    if (
        isinstance(maximum, bool)
        or not isinstance(maximum, (int, float))
        or not math.isfinite(maximum)
        or not 0 < maximum <= 1
    ):
        raise ReviewBufferError("max_source_share is invalid")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ReviewBufferError("buffer sources are invalid")
    resolved: list[_SourceConfig] = []
    source_ids: set[str] = set()
    paths: set[Path] = set()
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict) or set(raw) != _SOURCE_FIELDS:
            raise ReviewBufferError(f"buffer source {index} is invalid")
        source_id = raw.get("source_id")
        corpus_path = raw.get("corpus_path")
        expected_corpus_id = raw.get("expected_corpus_id")
        existing_path = raw.get("existing_corpus_path")
        expected_existing_id = raw.get("expected_existing_corpus_id")
        quota = raw.get("quota")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in source_ids
            or not isinstance(corpus_path, str)
            or not corpus_path
            or not isinstance(expected_corpus_id, str)
            or not expected_corpus_id
            or not isinstance(existing_path, str)
            or not existing_path
            or not isinstance(expected_existing_id, str)
            or not expected_existing_id
            or type(quota) is not int
            or quota < 1
        ):
            raise ReviewBufferError(f"buffer source {index} is invalid")
        candidate_path = (path.parent / corpus_path).resolve()
        prior_path = (path.parent / existing_path).resolve()
        if candidate_path == prior_path or candidate_path in paths or prior_path in paths:
            raise ReviewBufferError("buffer source paths must be unique")
        source_ids.add(source_id)
        paths.update((candidate_path, prior_path))
        resolved.append(
            _SourceConfig(
                source_id=source_id,
                corpus_path=candidate_path,
                expected_corpus_id=expected_corpus_id,
                existing_corpus_path=prior_path,
                expected_existing_corpus_id=expected_existing_id,
                quota=quota,
            )
        )
    payload["max_source_share"] = float(maximum)
    return payload, tuple(resolved)


def _load_review_corpus(path: Path, expected_corpus_id: str) -> list[dict[str, Any]]:
    try:
        validate_corpus_paths([path])
    except CorpusValidationError as exc:
        raise ReviewBufferError("buffer source violates the corpus contract") from exc
    payload = _read_object(path, "buffer source corpus")
    if payload.get("corpus_id") != expected_corpus_id:
        raise ReviewBufferError("buffer source corpus ID mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ReviewBufferError("buffer source contains no cases")
    resolved = cast(list[dict[str, Any]], cases)
    for case in resolved:
        source = cast(dict[str, Any], case["source"])
        if (
            case["label"] != "review"
            or case["expected_matches"] != []
            or case["slices"] != ["unadjudicated-intake"]
            or case["split"] != "tuning"
            or source["redistribution_allowed"] is not True
            or source["kind"] == "private"
        ):
            raise ReviewBufferError("buffer source must be blinded redistributable review data")
    return resolved


def _text_hash(text: str) -> bytes:
    return hashlib.sha256(text.encode("utf-8")).digest()


def _normalized_text_hash(text: str) -> bytes:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).digest()


def _validate_output_paths(
    config_path: Path,
    sources: Sequence[_SourceConfig],
    output_path: Path | None,
    report_path: Path | None,
) -> None:
    inputs = {
        config_path.resolve(),
        *(source.corpus_path for source in sources),
        *(source.existing_corpus_path for source in sources),
    }
    outputs = [path.resolve() for path in (output_path, report_path) if path is not None]
    if any(path in inputs for path in outputs) or len(set(outputs)) != len(outputs):
        raise ReviewBufferError("buffer outputs must not overwrite inputs or each other")


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewBufferError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise ReviewBufferError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReviewBufferError("failed to write buffer output") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Build a protected buffer while printing aggregate counts only."""

    arguments = _parser().parse_args(argv)
    try:
        result = build_review_buffer(
            arguments.config,
            output_path=arguments.output,
            report_path=arguments.report,
        )
    except ReviewBufferError as exc:
        print(f"review buffer planning failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"selected={result.report['selected_count']}; "
        f"maximum_source_share={result.report['maximum_observed_source_share']:.3f}; "
        "gold_ready=false"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
