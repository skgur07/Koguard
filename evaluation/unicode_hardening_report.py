"""Measure PF-012 Unicode accuracy slices and maximum-input cost."""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import sys
import tracemalloc
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter_ns
from typing import Any

from koguard import KoguardDictionary, KoguardEngine, ProfileName

DEFAULT_CORPUS_PATH = Path("tests/corpus/unicode_fp_cases.json")
DEFAULT_OUTPUT_PATH = Path("evaluation/results/pf012-unicode-hardening.report.json")
_BLACKLIST = ("시발", "병신")
_PERFORMANCE_PROFILE: ProfileName = "balanced"
_PERFORMANCE_CASES = (
    ("format-only-maximum", "\u200b" * 4096, 0),
    ("format-interleaved-clean-maximum", "가\u200b" * 2048, 0),
    ("format-obfuscated-positive-maximum", "\u200b" * 4093 + "시\u200b발", 1),
    ("combining-obfuscated-positive-maximum", "시" + "\u0301" * 4094 + "발", 1),
)


def _percentile(samples: Sequence[float], quantile: float) -> float:
    ordered = sorted(samples)
    return ordered[math.ceil(quantile * len(ordered)) - 1]


def _match_payload(match: Any) -> dict[str, object]:
    return {
        "term": match.term,
        "start": match.start,
        "end": match.end,
        "method": match.method.value,
    }


def _dictionary(whitelist: Sequence[str] = ()) -> KoguardDictionary:
    return KoguardDictionary.from_sources(
        blacklist=_BLACKLIST,
        whitelist=whitelist,
        include_defaults=False,
    )


def evaluate_accuracy(corpus_path: Path) -> dict[str, object]:
    """Return exact-match accuracy totals grouped by the public PF-012 slices."""

    document = json.loads(corpus_path.read_text(encoding="utf-8"))
    slices: dict[str, dict[str, int]] = defaultdict(
        lambda: {"cases": 0, "exact_cases": 0, "tp": 0, "fp": 0, "fn": 0}
    )
    for case in document["cases"]:
        engine = KoguardEngine(
            profile=case["profile"],
            dictionary=_dictionary(case.get("whitelist", ())),
        )
        actual = [_match_payload(match) for match in engine.check(case["text"]).matches]
        expected = case["expected_matches"]
        metrics = slices[case["slice"]]
        metrics["cases"] += 1
        metrics["exact_cases"] += actual == expected

        unmatched_actual = actual.copy()
        for expected_match in expected:
            if expected_match in unmatched_actual:
                metrics["tp"] += 1
                unmatched_actual.remove(expected_match)
            else:
                metrics["fn"] += 1
        metrics["fp"] += len(unmatched_actual)

    ordered_slices = {name: slices[name] for name in sorted(slices)}
    totals = {
        metric: sum(slice_metrics[metric] for slice_metrics in ordered_slices.values())
        for metric in ("cases", "exact_cases", "tp", "fp", "fn")
    }
    return {"totals": totals, "slices": ordered_slices}


def measure_performance(*, iterations: int, warmups: int) -> list[dict[str, object]]:
    """Measure fixed maximum-input workloads without hiding incorrect match counts."""

    results: list[dict[str, object]] = []
    for name, text, expected_matches_after_hardening in _PERFORMANCE_CASES:
        engine = KoguardEngine(profile=_PERFORMANCE_PROFILE, dictionary=_dictionary())
        for _ in range(warmups):
            engine.check(text)

        samples_ms: list[float] = []
        actual_matches = 0
        for _ in range(iterations):
            started_at = perf_counter_ns()
            result = engine.check(text)
            samples_ms.append((perf_counter_ns() - started_at) / 1_000_000)
            actual_matches = len(result.matches)

        tracemalloc.start()
        try:
            memory_result = engine.check(text)
            _, peak_memory_bytes = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()

        results.append(
            {
                "name": name,
                "profile": _PERFORMANCE_PROFILE,
                "input_length": len(text),
                "expected_matches_after_hardening": expected_matches_after_hardening,
                "actual_matches": actual_matches,
                "memory_actual_matches": len(memory_result.matches),
                "p50_ms": round(_percentile(samples_ms, 0.50), 4),
                "p95_ms": round(_percentile(samples_ms, 0.95), 4),
                "peak_memory_bytes": peak_memory_bytes,
            }
        )
    return results


def build_report(
    corpus_path: Path,
    *,
    iterations: int,
    warmups: int,
) -> dict[str, object]:
    """Build one machine-readable PF-012 report."""

    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    if warmups < 0:
        raise ValueError("warmups must be non-negative")
    return {
        "schema_version": 1,
        "measured_at": datetime.now(UTC).isoformat(),
        "environment": {
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
        },
        "configuration": {"iterations": iterations, "warmups": warmups},
        "accuracy": evaluate_accuracy(corpus_path),
        "performance": measure_performance(iterations=iterations, warmups=warmups),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmups", type=int, default=10)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the report and write it as UTF-8 JSON."""

    arguments = _parser().parse_args(argv)
    report = build_report(
        arguments.corpus,
        iterations=arguments.iterations,
        warmups=arguments.warmups,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote PF-012 report to {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
