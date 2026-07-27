"""Tests for the reproducible engine benchmark harness."""

import json
from pathlib import Path

import pytest
from benchmarks.engine_benchmark import (
    BenchmarkCase,
    BenchmarkError,
    load_cases,
    main,
    percentile,
    run_benchmarks,
)

from koguard import EngineConfig

CORPUS_PATH = Path("benchmarks/corpus.json")


def test_benchmark_corpus_covers_required_phase_two_scenarios() -> None:
    cases = load_cases(CORPUS_PATH)

    assert {case.category for case in cases} >= {
        "short-chat",
        "one-kilobyte",
        "maximum-input",
        "adversarial",
        "dictionary-scale",
    }
    assert max(len(case.text) for case in cases) == EngineConfig().max_input_length


def test_percentile_uses_nearest_rank() -> None:
    samples = [1.0, 2.0, 3.0, 4.0, 100.0]

    assert percentile(samples, 0.50) == 3.0
    assert percentile(samples, 0.95) == 100.0


def test_run_benchmarks_records_latency_throughput_memory_and_environment() -> None:
    case = BenchmarkCase(
        name="unit-clean",
        category="short-chat",
        text="안녕하세요",
        dictionary_size=2,
        expected_matches=0,
    )

    report = run_benchmarks((case,), iterations=3, warmups=1)

    assert report.environment.python_version.startswith("3.11.")
    assert report.environment.platform
    assert len(report.results) == 1
    result = report.results[0]
    assert result.name == "unit-clean"
    assert result.p50_ms > 0
    assert result.p95_ms >= result.p50_ms
    assert result.throughput_per_second > 0
    assert result.cold_start_ms > 0
    assert result.peak_memory_bytes > 0


def test_run_benchmarks_rejects_accuracy_regression() -> None:
    case = BenchmarkCase(
        name="wrong-expectation",
        category="short-chat",
        text="병신",
        dictionary_size=2,
        expected_matches=0,
    )

    with pytest.raises(BenchmarkError, match="expected 0 matches, got 1"):
        run_benchmarks((case,), iterations=1, warmups=0)


def test_benchmark_cli_writes_machine_readable_report(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus.json"
    output_path = tmp_path / "report.json"
    corpus_path.write_text(
        json.dumps(
            {
                "cases": [
                    {
                        "name": "cli-clean",
                        "category": "short-chat",
                        "text": "안녕하세요",
                        "dictionary_size": 2,
                        "expected_matches": 0,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--corpus",
            str(corpus_path),
            "--output",
            str(output_path),
            "--iterations",
            "2",
            "--warmups",
            "0",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["schema_version"] == 1
    assert payload["configuration"] == {"iterations": 2, "warmups": 0}
    assert payload["results"][0]["name"] == "cli-clean"
