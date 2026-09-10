"""Local before/after latency evidence; run separately before and after changes."""

import json
import statistics
import sys
from pathlib import Path
from time import perf_counter_ns

from koguard import KoguardEngine, ProfileName


def main() -> None:
    results: dict[str, dict[str, float]] = {}
    profiles: tuple[ProfileName, ...] = ("balanced", "aggressive")
    for profile in profiles:
        engine = KoguardEngine(profile=profile)
        for name, text in (
            ("clean_short", "오늘 날씨가 참 좋네요"),
            ("positive_short", "시발 하지 마"),
            ("clean_4096", "가" * 4096),
            ("positive_4096", "가" * 4094 + "시발"),
        ):
            rounds = []
            for _ in range(3):
                for _ in range(10):
                    engine.contains(text)
                samples = []
                for _ in range(100):
                    started = perf_counter_ns()
                    engine.contains(text)
                    samples.append((perf_counter_ns() - started) / 1_000_000)
                rounds.append(sorted(samples)[94])
            results[f"{profile}/{name}"] = {"p95_ms": statistics.median(rounds)}
    Path(sys.argv[1]).write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
