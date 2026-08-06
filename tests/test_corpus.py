"""Corpus-level regression tests for exact matching."""

import json
from collections import Counter
from pathlib import Path
from typing import TypedDict, cast

from koguard import EngineConfig, KoguardDictionary, KoguardEngine

_CORPUS_PATH = Path(__file__).parent / "corpus" / "exact_cases.json"
_WHITESPACE_GAP_CORPUS_PATH = Path(__file__).parent / "corpus" / "whitespace_gap_cases.json"
_CHOSEONG_CORPUS_PATH = Path(__file__).parent / "corpus" / "choseong_cases.json"
_ALIAS_CORPUS_PATH = Path(__file__).parent / "corpus" / "alias_cases.json"
_SEGMENTED_INPUT_CORPUS_PATH = Path(__file__).parent / "corpus" / "segmented_input_cases.json"


class ExactCase(TypedDict):
    id: str
    text: str
    expected_terms: list[str]


def _load_cases(path: Path = _CORPUS_PATH) -> list[ExactCase]:
    content = json.loads(path.read_text(encoding="utf-8"))
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


def test_whitespace_gap_corpus_has_no_false_positives_or_false_negatives() -> None:
    config = EngineConfig(whitespace_gap_matching=True, max_whitespace_gap=3)
    dictionary = KoguardDictionary.from_sources(
        blacklist=["시발", "개새끼", "병신"],
        include_defaults=False,
    )
    engine = KoguardEngine(config=config, dictionary=dictionary)
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for case in _load_cases(_WHITESPACE_GAP_CORPUS_PATH):
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


def test_choseong_corpus_has_no_false_positives_or_false_negatives() -> None:
    config = EngineConfig(choseong_matching=True)
    dictionary = KoguardDictionary.from_sources(
        blacklist=["시발", "씨발", "개새끼", "병신"],
        include_defaults=False,
    )
    engine = KoguardEngine(config=config, dictionary=dictionary)
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for case in _load_cases(_CHOSEONG_CORPUS_PATH):
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


def test_alias_corpus_has_no_false_positives_or_false_negatives() -> None:
    engine = KoguardEngine()
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for case in _load_cases(_ALIAS_CORPUS_PATH):
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


def test_segmented_input_corpus_has_no_false_positives_or_false_negatives() -> None:
    engine = KoguardEngine()
    true_positives = 0
    false_positives = 0
    false_negatives = 0

    for case in _load_cases(_SEGMENTED_INPUT_CORPUS_PATH):
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
