"""Integration tests for the synchronous Koguard engine."""

from concurrent.futures import ThreadPoolExecutor
from typing import cast

import pytest

from koguard import (
    ConfigurationError,
    EngineConfig,
    InputTooLongError,
    KoguardDictionary,
    KoguardEngine,
    MatchMethod,
)


def make_engine(
    *,
    blacklist: list[str],
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


def test_default_engine_detects_exact_term_with_original_span() -> None:
    text = "그 표현은 병신입니다"
    result = KoguardEngine().check(text)
    expected_start = text.index("병신")

    assert result.detected is True
    assert result.normalized_text == text
    assert len(result.matches) == 1
    assert result.matches[0].term == "병신"
    assert result.matches[0].matched_text == "병신"
    assert result.matches[0].start == expected_start
    assert result.matches[0].end == expected_start + 2
    assert result.matches[0].method is MatchMethod.EXACT
    assert result.matches[0].score == 1.0
    assert result.elapsed_ms >= 0.0


def test_default_engine_returns_clean_result() -> None:
    result = KoguardEngine().check("정상 문장입니다")

    assert result.detected is False
    assert result.matches == ()


def test_default_engine_detects_terms_inside_former_whitelist_examples() -> None:
    text = "시발점이지만 병신이라는 표현"
    result = KoguardEngine().check(text)

    assert [match.term for match in result.matches] == ["시발", "병신"]
    assert [match.start for match in result.matches] == [
        text.index("시발"),
        text.index("병신"),
    ]


def test_default_engine_detects_both_former_whitelist_examples() -> None:
    result = KoguardEngine().check("시발점과 병신년")

    assert [match.term for match in result.matches] == ["시발", "병신"]


def test_multiple_matches_are_sorted_by_original_position() -> None:
    text = "병신 그리고 시발"
    result = KoguardEngine().check(text)

    assert [match.term for match in result.matches] == ["병신", "시발"]
    assert [match.start for match in result.matches] == sorted(
        match.start for match in result.matches if match.start is not None
    )


def test_longest_overlapping_blacklist_term_wins() -> None:
    engine = make_engine(blacklist=["금칙", "금칙어"])

    result = engine.check("금칙어")

    assert [match.term for match in result.matches] == ["금칙어"]


def test_whitespace_normalization_preserves_original_match_span() -> None:
    engine = make_engine(blacklist=["금칙 어"])
    text = "앞 금칙\t\t어 뒤"

    result = engine.check(text)

    assert result.normalized_text == "앞 금칙 어 뒤"
    assert result.matches[0].matched_text == "금칙\t\t어"
    assert result.matches[0].start == text.index("금칙")
    assert result.matches[0].end == text.index("어") + 1


def test_nfkc_match_returns_original_compatibility_text() -> None:
    engine = make_engine(blacklist=["AB"])

    result = engine.check("ＡＢ")

    assert result.normalized_text == "AB"
    assert result.matches[0].matched_text == "ＡＢ"
    assert (result.matches[0].start, result.matches[0].end) == (0, 2)


def test_nfkc_expansion_deduplicates_original_match_span() -> None:
    engine = make_engine(blacklist=["f"])

    result = engine.check("ﬃ")

    assert result.normalized_text == "ffi"
    assert len(result.matches) == 1
    assert result.matches[0].matched_text == "ﬃ"
    assert (result.matches[0].start, result.matches[0].end) == (0, 1)


def test_whitelist_protects_shared_original_expansion_span() -> None:
    engine = make_engine(blacklist=["i"], whitelist=["f"])

    result = engine.check("ﬃ")

    assert result.detected is False


def test_overlapping_occurrences_produce_one_deterministic_match() -> None:
    engine = make_engine(blacklist=["aa"])

    result = engine.check("aaa")

    assert len(result.matches) == 1
    assert (result.matches[0].start, result.matches[0].end) == (0, 2)


def test_repeated_vowel_extension_is_detected_with_original_span() -> None:
    result = KoguardEngine().check("앞 시이이발 뒤")

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == "시이이발"
    assert result.matches[0].method is MatchMethod.REPEATED
    assert (result.matches[0].start, result.matches[0].end) == (2, 6)


def test_exact_match_keeps_priority_over_repeated_view() -> None:
    result = KoguardEngine().check("시발")

    assert len(result.matches) == 1
    assert result.matches[0].method is MatchMethod.EXACT


def test_exact_and_repeated_view_matches_are_both_preserved() -> None:
    result = KoguardEngine().check("시이이발 그리고 병신")

    assert [(match.term, match.method) for match in result.matches] == [
        ("시발", MatchMethod.REPEATED),
        ("병신", MatchMethod.EXACT),
    ]


def test_whitelist_protects_repeated_view_match() -> None:
    engine = make_engine(blacklist=["시발"], whitelist=["시발점"])

    result = engine.check("시이이발점")

    assert result.detected is False


def test_engine_rejects_non_string_input() -> None:
    invalid_text = cast(str, 123)

    with pytest.raises(TypeError, match="text must be a string"):
        KoguardEngine().check(invalid_text)


def test_engine_rejects_input_over_limit() -> None:
    engine = KoguardEngine(config=EngineConfig(max_input_length=3))

    with pytest.raises(InputTooLongError) as exc_info:
        engine.check("1234")

    assert exc_info.value.actual_length == 4
    assert exc_info.value.max_length == 3


def test_engine_rejects_dictionary_with_different_normalization() -> None:
    dictionary = KoguardDictionary.from_sources(
        include_defaults=False,
        unicode_form="NFC",
    )

    with pytest.raises(ConfigurationError, match="unicode_form"):
        KoguardEngine(config=EngineConfig(unicode_form="NFKC"), dictionary=dictionary)


def test_engine_is_safe_for_concurrent_checks() -> None:
    engine = KoguardEngine()
    texts = ["정상 문장", "시발점", "병신", "시발"] * 10

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(engine.check, texts))

    assert [result.detected for result in results] == [False, True, True, True] * 10
