"""Compose a deterministic, duplicate-free, multi-source review intake."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths

COMPOSITION_SCHEMA_PATH = Path(__file__).with_name("corpus-composition.schema.json")
COMPOSITION_REPORT_SCHEMA_PATH = Path(__file__).with_name("corpus-composition-report.schema.json")
_ID_FIELDS = frozenset(
    {
        "schema_version",
        "composition_id",
        "corpus_id",
        "split",
        "selection",
        "max_source_share",
        "sources",
    }
)
_SOURCE_FIELDS = frozenset({"source_id", "corpus_path", "expected_corpus_id", "quota"})


class CorpusCompositionError(ValueError):
    """Raised when balanced intake composition cannot be completed safely."""


@dataclass(frozen=True, slots=True)
class CorpusCompositionResult:
    """A composed review corpus and aggregate-only report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _SourceConfig:
    source_id: str
    path: Path
    expected_corpus_id: str
    quota: int


def compose_review_intake(
    config_path: Path,
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> CorpusCompositionResult:
    """Select configured source quotas while excluding direct and normalized overlap."""

    config, sources = _load_config(config_path)
    _validate_output_paths(config_path, sources, output_path, report_path)
    composition_id = cast(str, config["composition_id"])
    selected_cases: list[dict[str, Any]] = []
    selected_direct: set[bytes] = set()
    selected_normalized: set[bytes] = set()
    selected_ids: set[str] = set()
    source_rows: list[dict[str, Any]] = []

    for source in sources:
        cases = _load_review_corpus(source)
        ranked = sorted(
            cases,
            key=lambda case: (
                1 if case["label"] == "review" else 0,
                hashlib.sha256(
                    f"{composition_id}\0select\0{cast(str, case['id'])}".encode()
                ).hexdigest(),
                cast(str, case["id"]),
            ),
        )
        eligible: list[tuple[dict[str, Any], bytes, bytes]] = []
        local_direct: set[bytes] = set()
        local_normalized: set[bytes] = set()
        duplicate_count = 0
        for case in ranked:
            text = cast(str, case["text"])
            direct = hashlib.sha256(text.encode("utf-8")).digest()
            normalized = hashlib.sha256(
                unicodedata.normalize("NFKC", text).casefold().encode("utf-8")
            ).digest()
            if (
                direct in selected_direct
                or normalized in selected_normalized
                or direct in local_direct
                or normalized in local_normalized
            ):
                duplicate_count += 1
                continue
            local_direct.add(direct)
            local_normalized.add(normalized)
            eligible.append((case, direct, normalized))
        if len(eligible) < source.quota:
            raise CorpusCompositionError(
                f"source {source.source_id!r} has insufficient unique review cases"
            )
        chosen = eligible[: source.quota]
        for case, direct, normalized in chosen:
            case_id = cast(str, case["id"])
            if case_id in selected_ids:
                raise CorpusCompositionError("selected case IDs must be globally unique")
            selected_ids.add(case_id)
            selected_direct.add(direct)
            selected_normalized.add(normalized)
            selected_cases.append(case)
        source_rows.append(
            {
                "source_id": source.source_id,
                "available_count": len(cases),
                "selected_count": source.quota,
                "duplicate_excluded_count": duplicate_count,
                "share": 0.0,
            }
        )

    total = len(selected_cases)
    if total < 1:
        raise CorpusCompositionError("composition selected no cases")
    for row in source_rows:
        row["share"] = cast(int, row["selected_count"]) / total
    maximum_share = max(cast(float, row["share"]) for row in source_rows)
    configured_maximum = cast(float, config["max_source_share"])
    if maximum_share > configured_maximum + 1e-12:
        raise CorpusCompositionError("source share exceeds the configured maximum")
    composed_cases: list[dict[str, Any]] = []
    opaque_ids: set[str] = set()
    for case in selected_cases:
        original_id = cast(str, case["id"])
        opaque_id = (
            "review-"
            + hashlib.sha256(f"{composition_id}\0opaque\0{original_id}".encode()).hexdigest()[:24]
        )
        if opaque_id in opaque_ids:
            raise CorpusCompositionError("opaque composition ID collision")
        opaque_ids.add(opaque_id)
        composed = copy.deepcopy(case)
        composed["id"] = opaque_id
        composed_cases.append(composed)
    selected_cases = sorted(composed_cases, key=lambda case: cast(str, case["id"]))
    label_counts = Counter(cast(str, case["label"]) for case in selected_cases)
    finalized_count = label_counts["positive"] + label_counts["hard-negative"]
    corpus: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": config["corpus_id"],
        "cases": selected_cases,
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "composition_id": composition_id,
        "corpus_id": config["corpus_id"],
        "selected_count": total,
        "configured_max_source_share": configured_maximum,
        "maximum_observed_source_share": maximum_share,
        "source_bias_gate_passed": True,
        "source_statistics": source_rows,
        "generated_label_counts": {
            "positive": label_counts["positive"],
            "hard-negative": label_counts["hard-negative"],
            "review": label_counts["review"],
        },
        "adjudication_quality": {
            "carried_finalized": finalized_count,
            "pending_review": label_counts["review"],
        },
        "gold_ready": False,
        "completion_blockers": [
            "Pending selected cases still require independent double annotation.",
            "Disagreements require a separate adjudicator before gold promotion.",
            "Independent hidden evaluation is not part of this tuning composition.",
        ],
    }
    result = CorpusCompositionResult(corpus=corpus, report=report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _load_config(path: Path) -> tuple[dict[str, Any], tuple[_SourceConfig, ...]]:
    payload = _read_object(path, "composition configuration")
    if set(payload) != _ID_FIELDS or payload.get("schema_version") != 1:
        raise CorpusCompositionError("composition configuration violates version 1 contract")
    for name in ("composition_id", "corpus_id"):
        value = payload.get(name)
        if not isinstance(value, str) or not value or len(value) > 128:
            raise CorpusCompositionError(f"{name} is invalid")
    if payload.get("split") != "tuning" or payload.get("selection") != "stable-sha256-rank-v1":
        raise CorpusCompositionError("composition policy is unsupported")
    maximum = payload.get("max_source_share")
    if (
        isinstance(maximum, bool)
        or not isinstance(maximum, (int, float))
        or not math.isfinite(maximum)
        or not 0 < maximum <= 1
    ):
        raise CorpusCompositionError("max_source_share is invalid")
    raw_sources = payload.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise CorpusCompositionError("composition sources are invalid")
    sources: list[_SourceConfig] = []
    seen_ids: set[str] = set()
    seen_paths: set[Path] = set()
    for index, raw in enumerate(raw_sources):
        if not isinstance(raw, dict) or set(raw) != _SOURCE_FIELDS:
            raise CorpusCompositionError(f"composition source {index} is invalid")
        source_id = raw.get("source_id")
        corpus_path = raw.get("corpus_path")
        expected_corpus_id = raw.get("expected_corpus_id")
        quota = raw.get("quota")
        if (
            not isinstance(source_id, str)
            or not source_id
            or source_id in seen_ids
            or not isinstance(corpus_path, str)
            or not corpus_path
            or not isinstance(expected_corpus_id, str)
            or not expected_corpus_id
            or type(quota) is not int
            or quota < 1
        ):
            raise CorpusCompositionError(f"composition source {index} is invalid")
        resolved_path = (path.parent / corpus_path).resolve()
        if resolved_path in seen_paths:
            raise CorpusCompositionError("composition source paths must be unique")
        seen_ids.add(source_id)
        seen_paths.add(resolved_path)
        sources.append(
            _SourceConfig(
                source_id=source_id,
                path=resolved_path,
                expected_corpus_id=expected_corpus_id,
                quota=quota,
            )
        )
    payload["max_source_share"] = float(maximum)
    return payload, tuple(sources)


def _load_review_corpus(source: _SourceConfig) -> list[dict[str, Any]]:
    try:
        validate_corpus_paths([source.path])
    except CorpusValidationError as exc:
        raise CorpusCompositionError(
            f"source {source.source_id!r} failed corpus validation"
        ) from exc
    payload = _read_object(source.path, f"source {source.source_id!r}")
    if payload.get("corpus_id") != source.expected_corpus_id:
        raise CorpusCompositionError(f"source {source.source_id!r} corpus ID mismatch")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise CorpusCompositionError(f"source {source.source_id!r} contains no cases")
    resolved = cast(list[dict[str, Any]], cases)
    for case in resolved:
        source_data = cast(dict[str, Any], case["source"])
        if (
            case["split"] != "tuning"
            or source_data["redistribution_allowed"] is not True
            or source_data["kind"] == "private"
        ):
            raise CorpusCompositionError(
                f"source {source.source_id!r} must be tuning data and redistributable"
            )
        if case["label"] == "review" and (
            case["expected_matches"] != [] or case["slices"] != ["unadjudicated-intake"]
        ):
            raise CorpusCompositionError(
                f"source {source.source_id!r} review cases violate the pending contract"
            )
    return resolved


def _validate_output_paths(
    config_path: Path,
    sources: Sequence[_SourceConfig],
    output_path: Path | None,
    report_path: Path | None,
) -> None:
    inputs = {config_path.resolve(), *(source.path for source in sources)}
    outputs = [path.resolve() for path in (output_path, report_path) if path is not None]
    if any(path in inputs for path in outputs) or len(set(outputs)) != len(outputs):
        raise CorpusCompositionError("composition outputs must not overwrite inputs or each other")


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusCompositionError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise CorpusCompositionError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Compose configured sources and print aggregate counts only."""

    arguments = _parser().parse_args(argv)
    try:
        result = compose_review_intake(
            arguments.config,
            output_path=arguments.output,
            report_path=arguments.report,
        )
    except CorpusCompositionError as exc:
        print(f"corpus composition failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"selected={result.report['selected_count']}; "
        f"maximum_source_share={result.report['maximum_observed_source_share']:.3f}; "
        "gold_ready=false"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
