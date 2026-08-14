"""PF-012 Unicode, policy-FP, Whitelist, and span regression tests."""

import json
from collections import Counter
from pathlib import Path
from typing import Any, TypedDict, cast

import pytest
from evaluation.unicode_hardening_report import build_report

from koguard import KoguardDictionary, KoguardEngine, ProfileName


class ExpectedMatch(TypedDict):
    term: str
    start: int
    end: int
    method: str


class UnicodeCase(TypedDict, total=False):
    id: str
    slice: str
    profile: ProfileName
    text: str
    whitelist: list[str]
    expected_matches: list[ExpectedMatch]


_CORPUS_PATH = Path(__file__).parent / "corpus" / "unicode_fp_cases.json"
_AFTER_REPORT_PATH = (
    Path(__file__).parents[1] / "evaluation" / "results" / "pf012-after-windows-python311.json"
)
_BLACKLIST = ["시발", "병신"]
_MAXIMUM_INPUT_P95_LIMIT_MS = 15.0


def _load_cases() -> list[UnicodeCase]:
    document = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    assert document["schema_version"] == 1
    return cast(list[UnicodeCase], document["cases"])


def test_unicode_fp_corpus_preserves_policy_spans_and_whitelist() -> None:
    actual_by_slice: Counter[str] = Counter()
    expected_by_slice: Counter[str] = Counter()

    for case in _load_cases():
        dictionary = KoguardDictionary.from_sources(
            blacklist=_BLACKLIST,
            whitelist=case.get("whitelist", []),
            include_defaults=False,
        )
        result = KoguardEngine(profile=case["profile"], dictionary=dictionary).check(case["text"])
        actual = [
            {
                "term": match.term,
                "start": match.start,
                "end": match.end,
                "method": match.method.value,
            }
            for match in result.matches
        ]

        actual_by_slice[case["slice"]] += len(actual)
        expected_by_slice[case["slice"]] += len(case["expected_matches"])
        assert actual == case["expected_matches"], case["id"]

    assert actual_by_slice == expected_by_slice


def test_unicode_fp_corpus_has_unique_ids_and_required_policy_slices() -> None:
    cases = _load_cases()
    ids = [case["id"] for case in cases]

    assert len(ids) == len(set(ids))
    assert {case["slice"] for case in cases} == {
        "combining-positive",
        "compatibility-positive",
        "format-positive",
        "policy-hard-negative",
        "unicode-multiple",
        "whitelist-override",
    }


def test_unicode_hardening_report_records_accuracy_latency_and_memory() -> None:
    report = cast(dict[str, Any], build_report(_CORPUS_PATH, iterations=2, warmups=0))

    assert report["schema_version"] == 1
    assert report["configuration"] == {"iterations": 2, "warmups": 0}
    assert report["accuracy"]["totals"]["cases"] == len(_load_cases())
    performance = report["performance"]
    assert len(performance) == 4
    assert {result["profile"] for result in performance} == {"balanced"}
    assert {result["input_length"] for result in performance} == {4096}
    assert all(result["p95_ms"] >= result["p50_ms"] > 0 for result in performance)
    assert all(result["peak_memory_bytes"] > 0 for result in performance)


def test_committed_unicode_hardening_report_passes_release_slice_budgets() -> None:
    report = json.loads(_AFTER_REPORT_PATH.read_text(encoding="utf-8"))

    assert report["configuration"] == {"iterations": 100, "warmups": 10}
    assert report["accuracy"]["totals"] == {
        "cases": 20,
        "exact_cases": 20,
        "tp": 12,
        "fp": 0,
        "fn": 0,
    }
    assert all(
        result["profile"] == "balanced"
        and result["input_length"] == 4096
        and result["actual_matches"] == result["expected_matches_after_hardening"]
        and result["memory_actual_matches"] == result["expected_matches_after_hardening"]
        and result["p95_ms"] <= _MAXIMUM_INPUT_P95_LIMIT_MS
        for result in report["performance"]
    )


@pytest.mark.parametrize(
    ("iterations", "warmups", "message"),
    [(0, 0, "iterations"), (1, -1, "warmups")],
)
def test_unicode_hardening_report_rejects_invalid_measurement_counts(
    iterations: int,
    warmups: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_report(_CORPUS_PATH, iterations=iterations, warmups=warmups)
