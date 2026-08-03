"""Tests for the reproducible engine benchmark harness."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from benchmarks import engine_benchmark as benchmark_module
from benchmarks.engine_benchmark import (
    BenchmarkCase,
    BenchmarkError,
    benchmark_case_fingerprint,
    load_cases,
    main,
    percentile,
    run_benchmarks,
)

from koguard import EngineConfig

CORPUS_PATH = Path("benchmarks/corpus.json")
BASELINE_PATH = Path("benchmarks/results/windows-python311.json")


def test_benchmark_corpus_covers_required_phase_two_scenarios() -> None:
    cases = load_cases(CORPUS_PATH)

    assert {case.category for case in cases} >= {
        "short-chat",
        "one-kilobyte",
        "maximum-input",
        "adversarial",
        "dictionary-scale",
        "obfuscation",
        "whitespace-gap",
        "mixed-gap",
    }
    assert max(len(case.text) for case in cases) == EngineConfig().max_input_length
    assert {case.engine_profile for case in cases} >= {
        "default",
        "whitespace-gap",
    }
    assert any(
        case.engine_profile == "whitespace-gap"
        and case.dictionary_profile == "deep-whitespace-prefix"
        and len(case.text) == EngineConfig().max_input_length
        for case in cases
    )
    assert any(
        case.category == "mixed-gap"
        and case.dictionary_profile == "deep-whitespace-prefix"
        and len(case.text) == EngineConfig().max_input_length
        for case in cases
    )
    assert any(
        case.category == "dictionary-scale"
        and case.engine_profile == "whitespace-gap"
        and case.dictionary_size >= 1_000
        and case.expected_matches == 1
        for case in cases
    )


def test_percentile_uses_nearest_rank() -> None:
    samples = [1.0, 2.0, 3.0, 4.0, 100.0]

    assert percentile(samples, 0.50) == 3.0
    assert percentile(samples, 0.95) == 100.0


def test_benchmark_case_fingerprint_covers_complete_workload_definition() -> None:
    case = BenchmarkCase(
        name="fingerprint-case",
        category="whitespace-gap",
        text="시 발",
        dictionary_size=2,
        expected_matches=1,
        dictionary_profile="standard",
        engine_profile="whitespace-gap",
    )
    variants = (
        replace(case, name="renamed"),
        replace(case, category="short-chat"),
        replace(case, text="시  발"),
        replace(case, dictionary_size=3),
        replace(case, expected_matches=0),
        replace(case, dictionary_profile="deep-whitespace-prefix"),
        replace(case, engine_profile="default"),
    )

    fingerprint = benchmark_case_fingerprint(case)

    assert len(fingerprint) == 64
    assert fingerprint == benchmark_case_fingerprint(case)
    assert all(benchmark_case_fingerprint(variant) != fingerprint for variant in variants)


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
    assert result.engine_profile == "default"
    assert result.dictionary_profile == "standard"
    assert result.case_fingerprint == benchmark_case_fingerprint(case)
    assert result.p50_ms > 0
    assert result.p95_ms >= result.p50_ms
    assert result.throughput_per_second > 0
    assert result.cold_start_ms > 0
    assert result.peak_memory_bytes > 0
    assert result.engine_retained_memory_bytes > 0


def test_retained_memory_includes_opt_in_matcher_indexes() -> None:
    default_case = BenchmarkCase(
        name="unit-default-indexes",
        category="dictionary-scale",
        text="정상 문장",
        dictionary_size=100,
        expected_matches=0,
    )
    whitespace_case = replace(
        default_case,
        name="unit-whitespace-indexes",
        engine_profile="whitespace-gap",
    )

    report = run_benchmarks(
        (default_case, whitespace_case),
        iterations=1,
        warmups=0,
    )
    retained_by_profile = {
        result.engine_profile: result.engine_retained_memory_bytes for result in report.results
    }

    assert retained_by_profile["whitespace-gap"] > retained_by_profile["default"]


def test_retained_memory_is_invariant_to_prior_check_workload() -> None:
    short_case = BenchmarkCase(
        name="unit-retained-short",
        category="dictionary-scale",
        text="정상 문장",
        dictionary_size=2,
        expected_matches=0,
    )
    maximum_case = replace(
        short_case,
        name="unit-retained-maximum",
        text="가" * EngineConfig().max_input_length,
    )

    report = run_benchmarks(
        (short_case, maximum_case),
        iterations=100,
        warmups=10,
    )

    assert report.results[0].engine_retained_memory_bytes == (
        report.results[1].engine_retained_memory_bytes
    )


def test_retained_memory_starts_tracing_before_fresh_engine_creation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retained_allocation_size = 200_000

    class RetainedMemoryEngine:
        def __init__(self, **_: object) -> None:
            self.retained = bytearray(retained_allocation_size)

        def check(self, _text: str) -> object:
            return type("Result", (), {"matches": ()})()

    monkeypatch.setattr(benchmark_module, "KoguardEngine", RetainedMemoryEngine)
    case = BenchmarkCase(
        name="unit-retained-allocation",
        category="dictionary-scale",
        text="정상 문장",
        dictionary_size=2,
        expected_matches=0,
    )

    report = run_benchmarks((case,), iterations=1, warmups=0)

    assert report.results[0].engine_retained_memory_bytes >= retained_allocation_size


def test_run_benchmarks_applies_whitespace_gap_engine_profile() -> None:
    case = BenchmarkCase(
        name="unit-whitespace-gap",
        category="whitespace-gap",
        text="시 발",
        dictionary_size=2,
        expected_matches=1,
        engine_profile="whitespace-gap",
    )

    report = run_benchmarks((case,), iterations=2, warmups=0)

    assert report.results[0].engine_profile == "whitespace-gap"
    assert report.results[0].expected_matches == 1


def test_run_benchmarks_rejects_unknown_engine_profile() -> None:
    case = BenchmarkCase(
        name="unknown-profile",
        category="short-chat",
        text="정상 문장",
        dictionary_size=2,
        expected_matches=0,
        engine_profile="unknown",
    )

    with pytest.raises(BenchmarkError, match="unknown engine profile"):
        run_benchmarks((case,), iterations=1, warmups=0)


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
    assert payload["schema_version"] == 3
    assert payload["configuration"] == {"iterations": 2, "warmups": 0}
    assert payload["results"][0]["name"] == "cli-clean"
    assert payload["results"][0]["engine_profile"] == "default"
    assert payload["results"][0]["dictionary_profile"] == "standard"
    assert len(payload["results"][0]["case_fingerprint"]) == 64
    assert payload["results"][0]["engine_retained_memory_bytes"] > 0


def test_windows_baseline_matches_ordered_complete_corpus_cases() -> None:
    cases = load_cases(CORPUS_PATH)
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 3
    assert payload["environment"]["python_version"] == "3.11.9"
    assert payload["environment"]["implementation"] == "CPython"
    assert payload["environment"]["platform"].startswith("Windows-")
    assert payload["configuration"] == {"iterations": 100, "warmups": 10}
    assert [result["case_fingerprint"] for result in payload["results"]] == [
        benchmark_case_fingerprint(case) for case in cases
    ]
    assert all(result["engine_retained_memory_bytes"] > 0 for result in payload["results"])

    retained_by_engine: dict[tuple[str, str, int], int] = {}
    for result in payload["results"]:
        engine_key = (
            result["engine_profile"],
            result["dictionary_profile"],
            result["dictionary_size"],
        )
        retained_memory_bytes = result["engine_retained_memory_bytes"]
        assert retained_by_engine.setdefault(engine_key, retained_memory_bytes) == (
            retained_memory_bytes
        )
