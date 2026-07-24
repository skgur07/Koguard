"""Corpus-level regression tests for exact matching."""

import json
from collections import Counter
from pathlib import Path
from typing import TypedDict, cast

from koguard import KoguardEngine

_CORPUS_PATH = Path(__file__).parent / "corpus" / "exact_cases.json"


class ExactCase(TypedDict):
    id: str
    text: str
    expected_terms: list[str]


def _load_cases() -> list[ExactCase]:
    content = json.loads(_CORPUS_PATH.read_text(encoding="utf-8"))
    return cast(list[ExactCase], content)


def test_exact_corpus_has_no_false_positives_or_false_negatives() -> None:
    engine = KoguardEngine()
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for case in _load_cases():
        result = engine.check(case["text"])
        actual = Counter(match.term for match in result.matches)
        expected = Counter(case["expected_terms"])

        true_positives += sum((actual & expected).values())
        false_positives += sum((actual - expected).values())
        false_negatives += sum((expected - actual).values())

        assert list(match.term for match in result.matches) == case["expected_terms"], case["id"]

    precision = true_positives / (true_positives + false_positives)
    recall = true_positives / (true_positives + false_negatives)

    assert precision == 1.0
    assert recall == 1.0
