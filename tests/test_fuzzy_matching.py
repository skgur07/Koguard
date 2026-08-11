"""Integration tests for bounded Levenshtein matching."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from itertools import product

import pytest

from koguard import (
    ConfigurationError,
    EngineConfig,
    FuzzyOperationLimitError,
    KoguardDictionary,
    KoguardEngine,
    MatchMethod,
)


def make_engine(
    blacklist: list[str],
    *,
    whitelist: list[str] | None = None,
    config: EngineConfig | None = None,
) -> KoguardEngine:
    resolved_config = config or EngineConfig()
    dictionary = KoguardDictionary.from_sources(
        blacklist=blacklist,
        whitelist=whitelist or [],
        include_defaults=False,
        unicode_form=resolved_config.unicode_form,
    )
    return KoguardEngine(config=resolved_config, dictionary=dictionary)


@pytest.mark.parametrize(
    ("text", "expected_score"),
    [
        ("개세끼", 2 / 3),
        ("개끼", 2 / 3),
        ("개새애끼", 0.75),
    ],
)
def test_fuzzy_matching_detects_one_edit_with_original_span(
    text: str,
    expected_score: float,
) -> None:
    engine = make_engine(["개새끼"])

    result = engine.check(f"앞 {text} 뒤")

    assert len(result.matches) == 1
    match = result.matches[0]
    assert match.term == "개새끼"
    assert match.matched_text == text
    assert (match.start, match.end) == (2, 2 + len(text))
    assert match.method is MatchMethod.LEVENSHTEIN
    assert match.score == pytest.approx(expected_score)


def test_fuzzy_matching_can_be_disabled_independently() -> None:
    engine = make_engine(
        ["개새끼"],
        config=EngineConfig(fuzzy_matching=False),
    )

    assert engine.check("개세끼").detected is False


def test_fuzzy_matching_keeps_short_terms_exact_only() -> None:
    engine = make_engine(["시발", "병신"])

    assert engine.check("시팔").detected is False
    assert engine.check("빙신").detected is False


def test_fuzzy_matching_rejects_candidates_beyond_distance() -> None:
    engine = make_engine(["개새끼"])

    assert engine.check("개소리").detected is False


def test_fuzzy_matching_supports_configured_distance_two() -> None:
    engine = make_engine(
        ["개새끼"],
        config=EngineConfig(fuzzy_max_distance=2),
    )

    result = engine.check("개세기")

    assert result.matched_word == "개새끼"
    assert result.method is MatchMethod.LEVENSHTEIN
    assert result.confidence == pytest.approx(1 / 3)


def test_fuzzy_matching_honors_minimum_score() -> None:
    strict = make_engine(
        ["개새끼"],
        config=EngineConfig(fuzzy_min_score=0.7),
    )
    permissive = make_engine(
        ["개새끼"],
        config=EngineConfig(fuzzy_min_score=0.6),
    )

    assert strict.check("개세끼").detected is False
    assert permissive.check("개세끼").detected is True


def test_fuzzy_matching_does_not_treat_exact_input_as_fuzzy() -> None:
    engine = make_engine(
        ["개새끼"],
        config=EngineConfig(exact_matching=False),
    )

    assert engine.check("개새끼").detected is False


def test_rule_based_match_keeps_priority_over_fuzzy_match() -> None:
    engine = make_engine(["개새끼", "개세끼"])

    result = engine.check("개세끼")

    assert [(match.term, match.method) for match in result.matches] == [
        ("개세끼", MatchMethod.EXACT)
    ]


def test_fuzzy_matching_preserves_non_overlapping_exact_match() -> None:
    engine = make_engine(["개새끼", "돌아이"])

    result = engine.check("돌아이와 개세끼")

    assert [(match.term, match.method) for match in result.matches] == [
        ("돌아이", MatchMethod.EXACT),
        ("개새끼", MatchMethod.LEVENSHTEIN),
    ]


def test_exact_whitelist_span_protects_fuzzy_match() -> None:
    engine = make_engine(
        ["개새끼"],
        whitelist=["개세끼"],
    )

    assert engine.check("개세끼").detected is False


def test_fuzzy_matching_preserves_nfkc_original_span() -> None:
    engine = make_engine(["BAD"])

    result = engine.check("ＢＡＴ")

    assert result.matched_word == "BAD"
    assert result.matches[0].matched_text == "ＢＡＴ"
    assert (result.matches[0].start, result.matches[0].end) == (0, 3)


def test_fuzzy_matching_resolves_equal_candidates_deterministically() -> None:
    engine = make_engine(["가나다", "가마라"])

    result = engine.check("가나라")

    assert [match.term for match in result.matches] == ["가나다"]


def test_fuzzy_matching_does_not_cross_non_alphanumeric_boundaries() -> None:
    engine = make_engine(["개새끼"])

    assert engine.check("개-세끼").detected is False


def test_fuzzy_deletion_does_not_match_inside_larger_token() -> None:
    engine = make_engine(["개새끼"])

    assert engine.check("새끼손가락").detected is False


def test_fuzzy_substitution_does_not_match_inside_larger_token() -> None:
    engine = make_engine(["돌아이"])

    assert engine.check("돌아오는").detected is False


def test_fuzzy_matching_ignores_terms_above_configured_length() -> None:
    engine = make_engine(
        ["가나다라마바사"],
        config=EngineConfig(fuzzy_max_term_length=4),
    )

    assert engine.check("가나다라마바아").detected is False


def test_fuzzy_index_rejects_dictionary_above_configured_entry_limit() -> None:
    with pytest.raises(ConfigurationError, match="fuzzy_max_index_entries"):
        make_engine(
            ["가나다"],
            config=EngineConfig(fuzzy_max_index_entries=1),
        )


def test_fuzzy_matching_raises_when_operation_budget_is_exhausted() -> None:
    engine = make_engine(
        ["가나다", "가나마"],
        config=EngineConfig(fuzzy_max_operations=1),
    )

    with pytest.raises(FuzzyOperationLimitError) as exc_info:
        engine.check("가나라")

    assert exc_info.value.max_operations == 1


def test_fuzzy_matcher_is_safe_for_concurrent_checks() -> None:
    engine = make_engine(["개새끼"])

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(engine.check, ["개세끼", "정상문장"] * 10))

    assert [result.detected for result in results] == [True, False] * 10


def _reference_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    previous[right_index] + 1,
                    current[-1] + 1,
                    previous[right_index - 1] + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def test_fuzzy_matching_matches_exhaustive_one_edit_reference() -> None:
    alphabet = "abc"
    config = EngineConfig(
        exact_matching=False,
        repeated_matching=False,
        separator_matching=False,
        whitespace_gap_matching=False,
        mixed_gap_matching=False,
        choseong_matching=False,
        alias_matching=False,
        keyboard_matching=False,
        jamo_composition_matching=False,
        segmented_input_matching=False,
        fuzzy_matching=True,
    )

    for term_tuple in product(alphabet, repeat=3):
        term = "".join(term_tuple)
        engine = make_engine([term], config=config)
        for candidate_length in range(2, 5):
            for candidate_tuple in product(alphabet, repeat=candidate_length):
                candidate = "".join(candidate_tuple)
                if _reference_distance(term, candidate) != 1:
                    continue

                result = engine.check(candidate)

                assert result.matched_word == term, (term, candidate)
                assert result.method is MatchMethod.LEVENSHTEIN


def test_fuzzy_matching_matches_exhaustive_two_edit_reference() -> None:
    alphabet = "ab"
    config = EngineConfig(
        exact_matching=False,
        repeated_matching=False,
        separator_matching=False,
        whitespace_gap_matching=False,
        mixed_gap_matching=False,
        choseong_matching=False,
        alias_matching=False,
        keyboard_matching=False,
        jamo_composition_matching=False,
        segmented_input_matching=False,
        fuzzy_matching=True,
        fuzzy_max_distance=2,
    )

    for term_tuple in product(alphabet, repeat=3):
        term = "".join(term_tuple)
        engine = make_engine([term], config=config)
        for candidate_length in range(1, 6):
            for candidate_tuple in product(alphabet, repeat=candidate_length):
                candidate = "".join(candidate_tuple)
                if not 1 <= _reference_distance(term, candidate) <= 2:
                    continue

                result = engine.check(candidate)

                assert result.matched_word == term, (term, candidate)
                assert result.method is MatchMethod.LEVENSHTEIN
