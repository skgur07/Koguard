"""Measure matcher-level accuracy contribution, overlap, latency, and retained memory."""

from __future__ import annotations

import argparse
import copy
import gc
import json
import math
import os
import platform
import sys
import tracemalloc
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter_ns
from typing import Any, TypeAlias, cast

from evaluation.corpus_validator import CORPUS_SCHEMA_PATH, validate_corpus_paths
from koguard import EngineConfig, KoguardEngine, __version__

ABLATION_REPORT_SCHEMA_PATH = Path(__file__).with_name("ablation-report.schema.json")
DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus") / "provisional-ablation.json"
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("results") / "provisional-ablation.json"
ABLATION_MATCHERS = (
    "repeated",
    "separator",
    "whitespace",
    "mixed",
    "keyboard",
    "jamo",
    "choseong",
    "segmented",
    "fuzzy",
)
_MAX_INPUT_LENGTH = EngineConfig().max_input_length
_SHORT_CHAT = "오늘 저녁에 같이 게임할래?"
_MAXIMUM_PATTERN = "가나다라마바사아자차카타파하"

JsonScalar: TypeAlias = str | bool | int | float
OccurrenceKey: TypeAlias = tuple[str, int, int, str]


class AblationError(ValueError):
    """Raised when ablation input or measurement configuration is invalid."""


@dataclass(frozen=True, slots=True)
class ProfileDefinition:
    """One explicit matcher configuration and its comparison control."""

    profile_id: str
    role: str
    matcher: str | None
    comparison_profile: str | None
    config: EngineConfig


@dataclass(frozen=True, slots=True)
class AblationReport:
    """JSON-serializable ablation report."""

    _payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a defensive copy of the report payload."""

        return copy.deepcopy(self._payload)


@dataclass(frozen=True, slots=True)
class _GoldMatch:
    start: int
    end: int
    canonical_term: str


@dataclass(frozen=True, slots=True)
class _GoldCase:
    case_id: str
    text: str
    label: str
    matches: tuple[_GoldMatch, ...]
    slices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CorpusData:
    cases: tuple[_GoldCase, ...]
    file_ids: tuple[str, ...]
    sha256: str


@dataclass(frozen=True, slots=True)
class _ProfilePrediction:
    occurrences: frozenset[OccurrenceKey]
    counts_by_case: Mapping[str, int]


def _matcher_config(
    *,
    exact: bool = True,
    repeated: bool = False,
    separator: bool = False,
    whitespace: bool = False,
    mixed: bool = False,
    choseong: bool = False,
    alias: bool = True,
    keyboard: bool = False,
    jamo: bool = False,
    segmented: bool = False,
    fuzzy: bool = False,
) -> EngineConfig:
    return EngineConfig(
        exact_matching=exact,
        repeated_matching=repeated,
        separator_matching=separator,
        whitespace_gap_matching=whitespace,
        mixed_gap_matching=mixed,
        choseong_matching=choseong,
        alias_matching=alias,
        keyboard_matching=keyboard,
        jamo_composition_matching=jamo,
        segmented_input_matching=segmented,
        fuzzy_matching=fuzzy,
    )


def profile_definitions() -> tuple[ProfileDefinition, ...]:
    """Return every explicit profile used by PF-003 in deterministic order."""

    baseline = "exact-alias"
    return (
        ProfileDefinition(baseline, "baseline", None, None, _matcher_config()),
        ProfileDefinition(
            "repeated", "candidate", "repeated", baseline, _matcher_config(repeated=True)
        ),
        ProfileDefinition(
            "separator", "candidate", "separator", baseline, _matcher_config(separator=True)
        ),
        ProfileDefinition(
            "whitespace",
            "candidate",
            "whitespace",
            baseline,
            _matcher_config(whitespace=True),
        ),
        ProfileDefinition("mixed", "candidate", "mixed", baseline, _matcher_config(mixed=True)),
        ProfileDefinition(
            "keyboard", "candidate", "keyboard", baseline, _matcher_config(keyboard=True)
        ),
        ProfileDefinition("jamo", "candidate", "jamo", baseline, _matcher_config(jamo=True)),
        ProfileDefinition(
            "choseong", "candidate", "choseong", baseline, _matcher_config(choseong=True)
        ),
        ProfileDefinition(
            "segmented-prerequisites",
            "control",
            None,
            baseline,
            _matcher_config(choseong=True, keyboard=True, jamo=True),
        ),
        ProfileDefinition(
            "segmented",
            "candidate",
            "segmented",
            "segmented-prerequisites",
            _matcher_config(choseong=True, keyboard=True, jamo=True, segmented=True),
        ),
        ProfileDefinition("fuzzy", "candidate", "fuzzy", baseline, _matcher_config(fuzzy=True)),
        ProfileDefinition("all-enabled", "current", None, baseline, EngineConfig()),
    )


def run_ablation(
    corpus_paths: Sequence[Path],
    *,
    iterations: int = 100,
    warmups: int = 10,
    measured_at: datetime | None = None,
) -> AblationReport:
    """Run every PF-003 profile on one validated gold corpus and fixed workloads."""

    if iterations < 1:
        raise AblationError("iterations must be at least 1")
    if warmups < 0:
        raise AblationError("warmups must be non-negative")
    validate_corpus_paths(corpus_paths)
    corpus = _load_corpus(corpus_paths)
    cases = tuple(case for case in corpus.cases if case.label != "review")
    if not cases:
        raise AblationError("corpus contains no automatically evaluable cases")

    timestamp = measured_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise AblationError("measured_at must include timezone information")

    profiles = profile_definitions()
    workloads = _workload_texts()
    predictions = {profile.profile_id: _predict(profile, cases) for profile in profiles}
    performance = {
        profile.profile_id: _measure_performance(
            profile.config,
            workloads,
            iterations=iterations,
            warmups=warmups,
        )
        for profile in profiles
    }
    gold = _gold_occurrences(cases)
    candidate_additions = _candidate_additions(profiles, predictions)

    profile_results = [
        _profile_result(
            profile,
            cases,
            gold,
            predictions[profile.profile_id],
            performance[profile.profile_id],
        )
        for profile in profiles
    ]
    matcher_results = [
        _matcher_result(
            profile,
            cases,
            gold,
            predictions,
            candidate_additions,
            performance,
        )
        for profile in profiles
        if profile.role == "candidate"
    ]
    settings_payload = [
        {
            "profile_id": profile.profile_id,
            "comparison_profile": profile.comparison_profile,
            "settings": _config_settings(profile.config),
        }
        for profile in profiles
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "measured_at": timestamp.astimezone(UTC).isoformat(),
        "corpus": {
            "classification": "provisional-regression",
            "corpus_ids": list(corpus.file_ids),
            "sha256": corpus.sha256,
            "case_count": len(cases),
            "positive_count": sum(case.label == "positive" for case in cases),
            "hard_negative_count": sum(case.label == "hard-negative" for case in cases),
            "excluded_review_count": len(corpus.cases) - len(cases),
        },
        "environment": {
            "koguard_version": __version__,
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        },
        "configuration": {
            "iterations": iterations,
            "warmups": warmups,
            "profile_configuration_sha256": _canonical_sha256(settings_payload),
            "workloads": [
                {
                    "workload_id": workload_id,
                    "input_length": len(text),
                    "sha256": sha256(text.encode("utf-8")).hexdigest(),
                }
                for workload_id, text in workloads.items()
            ],
        },
        "profiles": profile_results,
        "matcher_ablation": matcher_results,
        "case_results": _case_results(cases, profiles, predictions),
        "limitations": [
            "구현 유래 20건 provisional regression corpus이므로 서비스 정확도를 대표하지 않는다.",
            "PF-005 독립 500/2,000 corpus에서 동일 runner를 재실행해야 "
            "balanced 결정을 확정할 수 있다.",
            "지연과 메모리는 단일 로컬 프로세스의 탐색적 측정이며 지원 OS별 CI 기준선이 아니다.",
        ],
    }
    return AblationReport(payload)


def _discover_corpus_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    schema_paths = {CORPUS_SCHEMA_PATH.resolve(), ABLATION_REPORT_SCHEMA_PATH.resolve()}
    discovered: set[Path] = set()
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            discovered.update(
                candidate.resolve()
                for candidate in path.rglob("*.json")
                if candidate.resolve() not in schema_paths
            )
        elif path.is_file() and path not in schema_paths:
            discovered.add(path)
    return tuple(sorted(discovered, key=lambda item: item.as_posix()))


def _load_corpus(paths: Sequence[Path]) -> _CorpusData:
    documents: list[tuple[str, dict[str, object]]] = []
    for path in _discover_corpus_files(paths):
        payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        documents.append((cast(str, payload["corpus_id"]), payload))

    cases: list[_GoldCase] = []
    canonical_documents: list[dict[str, object]] = []
    file_ids: list[str] = []
    for corpus_id, payload in sorted(documents, key=lambda item: item[0]):
        file_ids.append(corpus_id)
        canonical_documents.append(payload)
        for raw_case in cast(list[object], payload["cases"]):
            case = cast(dict[str, object], raw_case)
            matches = tuple(
                _GoldMatch(
                    start=cast(int, match["start"]),
                    end=cast(int, match["end"]),
                    canonical_term=cast(str, match["canonical_term"]),
                )
                for match in cast(list[dict[str, object]], case["expected_matches"])
            )
            cases.append(
                _GoldCase(
                    case_id=cast(str, case["id"]),
                    text=cast(str, case["text"]),
                    label=cast(str, case["label"]),
                    matches=matches,
                    slices=tuple(cast(list[str], case["slices"])),
                )
            )
    return _CorpusData(
        cases=tuple(cases),
        file_ids=tuple(file_ids),
        sha256=_canonical_sha256(canonical_documents),
    )


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(serialized).hexdigest()


def _config_settings(config: EngineConfig) -> dict[str, JsonScalar]:
    return {
        "alias_matching": config.alias_matching,
        "choseong_matching": config.choseong_matching,
        "exact_matching": config.exact_matching,
        "fuzzy_matching": config.fuzzy_matching,
        "fuzzy_max_distance": config.fuzzy_max_distance,
        "fuzzy_max_index_entries": config.fuzzy_max_index_entries,
        "fuzzy_max_operations": config.fuzzy_max_operations,
        "fuzzy_max_term_length": config.fuzzy_max_term_length,
        "fuzzy_min_score": config.fuzzy_min_score,
        "fuzzy_min_term_length": config.fuzzy_min_term_length,
        "jamo_composition_matching": config.jamo_composition_matching,
        "keyboard_matching": config.keyboard_matching,
        "max_input_length": config.max_input_length,
        "max_whitespace_gap": config.max_whitespace_gap,
        "mixed_gap_matching": config.mixed_gap_matching,
        "obfuscation_separators": "".join(sorted(config.obfuscation_separators)),
        "repeat_reduction_threshold": config.repeat_reduction_threshold,
        "repeated_matching": config.repeated_matching,
        "segmented_input_matching": config.segmented_input_matching,
        "separator_matching": config.separator_matching,
        "unicode_form": config.unicode_form,
        "whitespace_gap_matching": config.whitespace_gap_matching,
    }


def _predict(profile: ProfileDefinition, cases: Sequence[_GoldCase]) -> _ProfilePrediction:
    engine = KoguardEngine(config=profile.config)
    occurrences: set[OccurrenceKey] = set()
    counts_by_case: dict[str, int] = {}
    for case in cases:
        result = engine.check(case.text)
        count = 0
        for match in result.matches:
            if match.start is None or match.end is None:
                raise AblationError(
                    f"profile {profile.profile_id} returned a match without an original span"
                )
            occurrences.add((case.case_id, match.start, match.end, match.term))
            count += 1
        counts_by_case[case.case_id] = count
    return _ProfilePrediction(frozenset(occurrences), counts_by_case)


def _gold_occurrences(cases: Sequence[_GoldCase]) -> frozenset[OccurrenceKey]:
    return frozenset(
        (case.case_id, match.start, match.end, match.canonical_term)
        for case in cases
        for match in case.matches
    )


def _metric_payload(tp: int, fp: int, fn: int, *, tn: int | None = None) -> dict[str, Any]:
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    counts: dict[str, int] = {"tp": tp, "fp": fp, "fn": fn}
    if tn is not None:
        counts["tn"] = tn
    payload: dict[str, Any] = {
        "counts": counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
    if tn is not None:
        payload["accuracy"] = (tp + tn) / (tp + fp + fn + tn)
    return payload


def _sentence_outcome(gold_detected: bool, detected: bool) -> str:
    if gold_detected:
        return "tp" if detected else "fn"
    return "fp" if detected else "tn"


def _sentence_metrics(cases: Sequence[_GoldCase], prediction: _ProfilePrediction) -> dict[str, Any]:
    counts: Counter[str] = Counter(
        _sentence_outcome(bool(case.matches), prediction.counts_by_case[case.case_id] > 0)
        for case in cases
    )
    return _metric_payload(counts["tp"], counts["fp"], counts["fn"], tn=counts["tn"])


def _occurrence_metrics(
    gold: frozenset[OccurrenceKey], prediction: _ProfilePrediction
) -> dict[str, Any]:
    true_positive = len(gold & prediction.occurrences)
    return _metric_payload(
        true_positive,
        len(prediction.occurrences - gold),
        len(gold - prediction.occurrences),
    )


def _slice_metrics(
    cases: Sequence[_GoldCase],
    gold: frozenset[OccurrenceKey],
    prediction: _ProfilePrediction,
) -> list[dict[str, Any]]:
    results = []
    for slice_name in sorted({slice_name for case in cases for slice_name in case.slices}):
        slice_cases = tuple(case for case in cases if slice_name in case.slices)
        case_ids = {case.case_id for case in slice_cases}
        slice_gold = frozenset(item for item in gold if item[0] in case_ids)
        slice_prediction = _ProfilePrediction(
            frozenset(item for item in prediction.occurrences if item[0] in case_ids),
            prediction.counts_by_case,
        )
        results.append(
            {
                "slice": slice_name,
                "case_count": len(slice_cases),
                "sentence_metrics": _sentence_metrics(slice_cases, prediction),
                "occurrence_metrics": _occurrence_metrics(slice_gold, slice_prediction),
            }
        )
    return results


def _percentile(samples: Sequence[float], quantile: float) -> float:
    ordered = sorted(samples)
    rank = math.ceil(quantile * len(ordered))
    return ordered[rank - 1]


def _measure_workload(
    engine: KoguardEngine,
    text: str,
    *,
    iterations: int,
    warmups: int,
) -> dict[str, Any]:
    for _ in range(warmups):
        engine.check(text)
    samples = []
    for _ in range(iterations):
        started_at = perf_counter_ns()
        engine.check(text)
        samples.append((perf_counter_ns() - started_at) / 1_000_000)
    return {
        "input_length": len(text),
        "p50_ms": _percentile(samples, 0.50),
        "p95_ms": _percentile(samples, 0.95),
    }


def _measure_retained_memory(config: EngineConfig) -> int:
    gc.collect()
    tracemalloc.start()
    try:
        engine = KoguardEngine(config=config)
        retained, _ = tracemalloc.get_traced_memory()
        del engine
    finally:
        tracemalloc.stop()
    return retained


def _measure_performance(
    config: EngineConfig,
    workloads: Mapping[str, str],
    *,
    iterations: int,
    warmups: int,
) -> dict[str, Any]:
    engine = KoguardEngine(config=config)
    return {
        "short_chat": _measure_workload(
            engine, workloads["short_chat"], iterations=iterations, warmups=warmups
        ),
        "maximum_input": _measure_workload(
            engine, workloads["maximum_input"], iterations=iterations, warmups=warmups
        ),
        "engine_retained_memory_bytes": _measure_retained_memory(config),
    }


def _workload_texts() -> dict[str, str]:
    maximum_input = (_MAXIMUM_PATTERN * math.ceil(_MAX_INPUT_LENGTH / len(_MAXIMUM_PATTERN)))[
        :_MAX_INPUT_LENGTH
    ]
    return {
        "short_chat": _SHORT_CHAT,
        "maximum_input": maximum_input,
    }


def _profile_result(
    profile: ProfileDefinition,
    cases: Sequence[_GoldCase],
    gold: frozenset[OccurrenceKey],
    prediction: _ProfilePrediction,
    performance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "profile_id": profile.profile_id,
        "role": profile.role,
        "matcher": profile.matcher,
        "comparison_profile": profile.comparison_profile,
        "settings": _config_settings(profile.config),
        "sentence_metrics": _sentence_metrics(cases, prediction),
        "occurrence_metrics": _occurrence_metrics(gold, prediction),
        "slice_metrics": _slice_metrics(cases, gold, prediction),
        "performance": performance,
    }


def _candidate_additions(
    profiles: Sequence[ProfileDefinition],
    predictions: Mapping[str, _ProfilePrediction],
) -> dict[str, frozenset[OccurrenceKey]]:
    additions = {}
    for profile in profiles:
        if profile.role != "candidate" or profile.matcher is None:
            continue
        if profile.comparison_profile is None:
            raise AblationError(f"candidate {profile.profile_id} has no comparison profile")
        additions[profile.matcher] = frozenset(
            predictions[profile.profile_id].occurrences
            - predictions[profile.comparison_profile].occurrences
        )
    return additions


def _matcher_result(
    profile: ProfileDefinition,
    cases: Sequence[_GoldCase],
    gold: frozenset[OccurrenceKey],
    predictions: Mapping[str, _ProfilePrediction],
    candidate_additions: Mapping[str, frozenset[OccurrenceKey]],
    performance: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    if profile.matcher is None or profile.comparison_profile is None:
        raise AblationError(f"invalid candidate profile: {profile.profile_id}")
    predicted = predictions[profile.profile_id].occurrences
    baseline = predictions[profile.comparison_profile].occurrences
    added = candidate_additions[profile.matcher]
    removed = baseline - predicted
    other_added = frozenset(
        item
        for matcher, occurrences in candidate_additions.items()
        if matcher != profile.matcher
        for item in occurrences
    )
    cross_overlap = added & other_added
    unique_added = added - other_added
    added_tp = added & gold
    added_fp = added - gold
    resolved_slices: Counter[str] = Counter()
    resolved_case_ids = {item[0] for item in added_tp}
    for case in cases:
        if case.case_id in resolved_case_ids:
            resolved_slices.update(case.slices)
    profile_cost = performance[profile.profile_id]
    baseline_cost = performance[profile.comparison_profile]
    return {
        "matcher": profile.matcher,
        "profile_id": profile.profile_id,
        "comparison_profile": profile.comparison_profile,
        "contribution": {
            "added_tp": len(added_tp),
            "added_fp": len(added_fp),
            "removed_tp": len(removed & gold),
            "removed_fp": len(removed - gold),
            "baseline_overlap": len(predicted & baseline),
            "cross_matcher_overlap": len(cross_overlap),
            "unique_added": len(unique_added),
            "unique_added_tp": len(unique_added & gold),
            "unique_added_fp": len(unique_added - gold),
            "remaining_fn": len(gold - predicted),
        },
        "resolved_false_negative_slices": [
            {"slice": name, "count": count} for name, count in sorted(resolved_slices.items())
        ],
        "new_false_positive_case_ids": sorted({item[0] for item in added_fp}),
        "cost_delta": {
            "short_chat_p50_ms": profile_cost["short_chat"]["p50_ms"]
            - baseline_cost["short_chat"]["p50_ms"],
            "short_chat_p95_ms": profile_cost["short_chat"]["p95_ms"]
            - baseline_cost["short_chat"]["p95_ms"],
            "maximum_input_p50_ms": profile_cost["maximum_input"]["p50_ms"]
            - baseline_cost["maximum_input"]["p50_ms"],
            "maximum_input_p95_ms": profile_cost["maximum_input"]["p95_ms"]
            - baseline_cost["maximum_input"]["p95_ms"],
            "engine_retained_memory_bytes": profile_cost["engine_retained_memory_bytes"]
            - baseline_cost["engine_retained_memory_bytes"],
        },
    }


def _case_results(
    cases: Sequence[_GoldCase],
    profiles: Sequence[ProfileDefinition],
    predictions: Mapping[str, _ProfilePrediction],
) -> list[dict[str, Any]]:
    results = []
    for case in cases:
        results.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "slices": list(case.slices),
                "gold_occurrence_count": len(case.matches),
                "profiles": [
                    {
                        "profile_id": profile.profile_id,
                        "detected": predictions[profile.profile_id].counts_by_case[case.case_id]
                        > 0,
                        "sentence_outcome": _sentence_outcome(
                            bool(case.matches),
                            predictions[profile.profile_id].counts_by_case[case.case_id] > 0,
                        ),
                        "predicted_occurrence_count": predictions[
                            profile.profile_id
                        ].counts_by_case[case.case_id],
                    }
                    for profile in profiles
                ],
            }
        )
    return results


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", nargs="+", type=Path, default=[DEFAULT_CORPUS_PATH])
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run matcher ablation and write a machine-readable report."""

    arguments = _parser().parse_args(argv)
    try:
        report = run_ablation(
            arguments.corpus,
            iterations=arguments.iterations,
            warmups=arguments.warmups,
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (AblationError, OSError, ValueError) as exc:
        print(f"ablation failed: {exc}", file=sys.stderr)
        return 1
    print(f"ablation report written: {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
