"""Measure Koguard latency, throughput, cold start, and peak memory."""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import platform
import sys
import tracemalloc
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from koguard import AliasMode, AliasRule, EngineConfig, KoguardDictionary, KoguardEngine

DEFAULT_CORPUS_PATH = Path(__file__).with_name("corpus.json")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("results") / "latest.json"
_ENGINE_PROFILES = frozenset(
    {"alias", "choseong", "default", "minimal", "segmented-input", "whitespace-gap"}
)
_HANGUL_SYLLABLE_BASE = 0xAC00
_HANGUL_SYLLABLES_PER_LEADING = 588
_LEADING_SYLLABLE_DIGITS = tuple(
    chr(_HANGUL_SYLLABLE_BASE + index * _HANGUL_SYLLABLES_PER_LEADING) for index in range(19)
)


class BenchmarkError(ValueError):
    """Raised when a benchmark case or measured result is invalid."""


@dataclass(frozen=True, slots=True)
class BenchmarkCase:
    """One reproducible workload and its correctness expectation."""

    name: str
    category: str
    text: str
    dictionary_size: int
    expected_matches: int
    dictionary_profile: str = "standard"
    engine_profile: str = "default"


def benchmark_case_fingerprint(case: BenchmarkCase) -> str:
    """Return a stable digest covering the complete semantic workload."""

    serialized = json.dumps(
        asdict(case),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class BenchmarkEnvironment:
    """Runtime metadata required to interpret benchmark results."""

    python_version: str
    implementation: str
    platform: str
    processor: str


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """Metrics recorded for one benchmark case."""

    name: str
    category: str
    engine_profile: str
    dictionary_profile: str
    case_fingerprint: str
    input_length: int
    dictionary_size: int
    expected_matches: int
    p50_ms: float
    p95_ms: float
    throughput_per_second: float
    cold_start_ms: float
    peak_memory_bytes: int
    engine_retained_memory_bytes: int


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    """Machine-readable benchmark report."""

    schema_version: int
    measured_at: str
    environment: BenchmarkEnvironment
    iterations: int
    warmups: int
    results: tuple[BenchmarkResult, ...]

    def to_dict(self) -> dict[str, Any]:
        """Convert the report to its stable JSON representation."""

        return {
            "schema_version": self.schema_version,
            "measured_at": self.measured_at,
            "environment": asdict(self.environment),
            "configuration": {
                "iterations": self.iterations,
                "warmups": self.warmups,
            },
            "results": [asdict(result) for result in self.results],
        }


def percentile(samples: Sequence[float], quantile: float) -> float:
    """Return a nearest-rank percentile from non-empty samples."""

    if not samples:
        raise BenchmarkError("samples must not be empty")
    if not 0 < quantile <= 1:
        raise BenchmarkError("quantile must satisfy 0 < quantile <= 1")
    ordered = sorted(samples)
    rank = math.ceil(quantile * len(ordered))
    return ordered[rank - 1]


def _require_int(payload: dict[str, object], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise BenchmarkError(f"{key} must be an integer")
    return value


def _require_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise BenchmarkError(f"{key} must be a non-empty string")
    return value


def _case_from_payload(payload: object) -> BenchmarkCase:
    if not isinstance(payload, dict):
        raise BenchmarkError("each benchmark case must be an object")

    typed_payload: dict[str, object] = payload
    text_value = typed_payload.get("text")
    pattern_value = typed_payload.get("text_pattern")
    if isinstance(text_value, str):
        text = text_value
    elif isinstance(pattern_value, str) and pattern_value:
        length = _require_int(typed_payload, "length")
        if length < 0:
            raise BenchmarkError("length must be non-negative")
        repeats = math.ceil(length / len(pattern_value)) if length else 0
        text = (pattern_value * repeats)[:length]
    else:
        raise BenchmarkError("case requires text or non-empty text_pattern")

    dictionary_profile = typed_payload.get("dictionary_profile", "standard")
    if not isinstance(dictionary_profile, str):
        raise BenchmarkError("dictionary_profile must be a string")
    engine_profile = typed_payload.get("engine_profile", "default")
    if not isinstance(engine_profile, str):
        raise BenchmarkError("engine_profile must be a string")

    case = BenchmarkCase(
        name=_require_string(typed_payload, "name"),
        category=_require_string(typed_payload, "category"),
        text=text,
        dictionary_size=_require_int(typed_payload, "dictionary_size"),
        expected_matches=_require_int(typed_payload, "expected_matches"),
        dictionary_profile=dictionary_profile,
        engine_profile=engine_profile,
    )
    if case.dictionary_size < 2:
        raise BenchmarkError("dictionary_size must be at least 2")
    if case.expected_matches < 0:
        raise BenchmarkError("expected_matches must be non-negative")
    if case.engine_profile not in _ENGINE_PROFILES:
        raise BenchmarkError(f"unknown engine profile: {case.engine_profile}")
    return case


def load_cases(path: Path) -> tuple[BenchmarkCase, ...]:
    """Load and validate benchmark cases from a UTF-8 JSON corpus."""

    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"failed to load benchmark corpus: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise BenchmarkError("benchmark corpus must contain a cases array")

    cases = tuple(_case_from_payload(item) for item in payload["cases"])
    if not cases:
        raise BenchmarkError("benchmark corpus must contain at least one case")
    if len({case.name for case in cases}) != len(cases):
        raise BenchmarkError("benchmark case names must be unique")
    return cases


def _choseong_scale_term(index: int) -> str:
    """Return an all-Hangul term with a unique choseong suffix."""

    digits: list[str] = []
    value = index
    while True:
        digits.append(_LEADING_SYLLABLE_DIGITS[value % len(_LEADING_SYLLABLE_DIGITS)])
        value //= len(_LEADING_SYLLABLE_DIGITS)
        if value == 0:
            break
    return "합성" + "".join(reversed(digits))


def _dictionary_for(case: BenchmarkCase) -> KoguardDictionary:
    aliases: tuple[AliasRule, ...] = ()
    if case.dictionary_profile == "overlapping-prefix":
        blacklist = ["a" * size for size in range(1, case.dictionary_size + 1)]
    elif case.dictionary_profile == "deep-whitespace-prefix":
        blacklist = ["a" * size for size in range(2, case.dictionary_size + 2)]
    elif case.dictionary_profile == "choseong-scale":
        blacklist = ["병신", "시발"]
        blacklist.extend(_choseong_scale_term(index) for index in range(case.dictionary_size - 2))
    elif case.dictionary_profile == "alias":
        blacklist = ["좆같다", "병신"]
        blacklist.extend(f"합성금칙어{index:06d}" for index in range(case.dictionary_size - 2))
        aliases = (AliasRule("ㅈ같", "좆같다", AliasMode.TOKEN_PREFIX),)
    elif case.dictionary_profile == "standard":
        blacklist = ["병신", "시발"]
        blacklist.extend(f"합성금칙어{index:06d}" for index in range(case.dictionary_size - 2))
    else:
        raise BenchmarkError(f"unknown dictionary profile: {case.dictionary_profile}")

    return KoguardDictionary.from_sources(
        blacklist=blacklist,
        whitelist=["병신년", "시발점"],
        aliases=aliases,
        include_defaults=False,
    )


def _config_for(case: BenchmarkCase) -> EngineConfig:
    if case.engine_profile == "default":
        return EngineConfig()
    if case.engine_profile == "minimal":
        return EngineConfig(
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=False,
            mixed_gap_matching=False,
            choseong_matching=False,
            alias_matching=False,
            keyboard_matching=False,
            jamo_composition_matching=False,
            segmented_input_matching=False,
        )
    if case.engine_profile == "whitespace-gap":
        return EngineConfig(
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=True,
            mixed_gap_matching=True,
            choseong_matching=False,
            alias_matching=False,
            keyboard_matching=False,
            jamo_composition_matching=False,
            segmented_input_matching=False,
        )
    if case.engine_profile == "choseong":
        return EngineConfig(
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=False,
            mixed_gap_matching=False,
            choseong_matching=True,
            alias_matching=False,
            keyboard_matching=False,
            jamo_composition_matching=False,
            segmented_input_matching=False,
        )
    if case.engine_profile == "alias":
        return EngineConfig(
            exact_matching=False,
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=False,
            mixed_gap_matching=False,
            choseong_matching=False,
            alias_matching=True,
            keyboard_matching=False,
            jamo_composition_matching=False,
            segmented_input_matching=False,
        )
    if case.engine_profile == "segmented-input":
        return EngineConfig(
            exact_matching=False,
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=False,
            mixed_gap_matching=False,
            choseong_matching=True,
            alias_matching=False,
            keyboard_matching=True,
            jamo_composition_matching=True,
            segmented_input_matching=True,
        )
    raise BenchmarkError(f"unknown engine profile: {case.engine_profile}")


def _validate_result(case: BenchmarkCase, match_count: int) -> None:
    if match_count != case.expected_matches:
        raise BenchmarkError(
            f"{case.name}: expected {case.expected_matches} matches, got {match_count}"
        )


def _measure_engine_retained_memory(case: BenchmarkCase) -> int:
    """Return isolated Python allocations retained by a fresh engine."""

    # CPython's full collection also clears several built-in free lists. Run it before
    # tracing so earlier benchmark workloads cannot change the retained-memory result.
    gc.collect()
    tracemalloc.start()
    try:
        engine = KoguardEngine(
            config=_config_for(case),
            dictionary=_dictionary_for(case),
        )
        retained_memory_bytes, _ = tracemalloc.get_traced_memory()
        del engine
    finally:
        tracemalloc.stop()
    return retained_memory_bytes


def _measure_case(
    case: BenchmarkCase,
    *,
    iterations: int,
    warmups: int,
) -> BenchmarkResult:
    cold_started_at = perf_counter_ns()
    engine = KoguardEngine(
        config=_config_for(case),
        dictionary=_dictionary_for(case),
    )
    cold_result = engine.check(case.text)
    cold_start_ms = (perf_counter_ns() - cold_started_at) / 1_000_000
    _validate_result(case, len(cold_result.matches))

    for _ in range(warmups):
        _validate_result(case, len(engine.check(case.text).matches))

    samples_ms: list[float] = []
    for _ in range(iterations):
        started_at = perf_counter_ns()
        result = engine.check(case.text)
        samples_ms.append((perf_counter_ns() - started_at) / 1_000_000)
        _validate_result(case, len(result.matches))

    tracemalloc.start()
    try:
        memory_result = engine.check(case.text)
        _, peak_memory_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    _validate_result(case, len(memory_result.matches))
    engine_retained_memory_bytes = _measure_engine_retained_memory(case)

    total_seconds = sum(samples_ms) / 1_000
    return BenchmarkResult(
        name=case.name,
        category=case.category,
        engine_profile=case.engine_profile,
        dictionary_profile=case.dictionary_profile,
        case_fingerprint=benchmark_case_fingerprint(case),
        input_length=len(case.text),
        dictionary_size=case.dictionary_size,
        expected_matches=case.expected_matches,
        p50_ms=percentile(samples_ms, 0.50),
        p95_ms=percentile(samples_ms, 0.95),
        throughput_per_second=iterations / total_seconds,
        cold_start_ms=cold_start_ms,
        peak_memory_bytes=peak_memory_bytes,
        engine_retained_memory_bytes=engine_retained_memory_bytes,
    )


def _environment() -> BenchmarkEnvironment:
    processor = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown")
    return BenchmarkEnvironment(
        python_version=platform.python_version(),
        implementation=platform.python_implementation(),
        platform=platform.platform(),
        processor=processor,
    )


def run_benchmarks(
    cases: Sequence[BenchmarkCase],
    *,
    iterations: int,
    warmups: int,
) -> BenchmarkReport:
    """Run cases sequentially and return a reproducible report."""

    if not cases:
        raise BenchmarkError("cases must not be empty")
    if iterations < 1:
        raise BenchmarkError("iterations must be at least 1")
    if warmups < 0:
        raise BenchmarkError("warmups must be non-negative")

    results = tuple(_measure_case(case, iterations=iterations, warmups=warmups) for case in cases)
    return BenchmarkReport(
        schema_version=3,
        measured_at=datetime.now(UTC).isoformat(),
        environment=_environment(),
        iterations=iterations,
        warmups=warmups,
        results=results,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark CLI and write a JSON report."""

    arguments = _parser().parse_args(argv)
    report = run_benchmarks(
        load_cases(arguments.corpus),
        iterations=arguments.iterations,
        warmups=arguments.warmups,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(report.results)} benchmark results to {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
