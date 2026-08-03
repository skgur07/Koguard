"""Integration tests for the synchronous Koguard engine."""

from concurrent.futures import ThreadPoolExecutor
from typing import cast
from unittest.mock import patch

import pytest

from koguard import (
    ConfigurationError,
    EngineConfig,
    InputTooLongError,
    KoguardDictionary,
    KoguardEngine,
    MatchMethod,
)
from koguard.engine import matcher as matcher_module


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


def test_special_character_obfuscation_is_detected_with_original_span() -> None:
    result = KoguardEngine().check("앞 시*!발 뒤")

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == "시*!발"
    assert result.matches[0].method is MatchMethod.SEPARATOR
    assert (result.matches[0].start, result.matches[0].end) == (2, 6)


def test_exact_match_keeps_priority_over_separator_view() -> None:
    result = KoguardEngine().check("시발")

    assert len(result.matches) == 1
    assert result.matches[0].method is MatchMethod.EXACT


def test_whitelist_protects_separator_view_match() -> None:
    engine = make_engine(blacklist=["시발"], whitelist=["시발점"])

    result = engine.check("시*발점")

    assert result.detected is False


def test_separator_view_whitelist_protects_overlapping_exact_view_match() -> None:
    config = EngineConfig(obfuscation_separators=frozenset({"-"}))
    engine = make_engine(
        blacklist=["ab", "abcd"],
        whitelist=["abcd"],
        config=config,
    )

    result = engine.check("ab-cd")

    assert result.detected is False
    assert result.matches == ()


def test_global_whitelist_falls_back_to_shorter_exact_candidate() -> None:
    text = "시이이X바아아보"
    engine = make_engine(
        blacklist=["시이이", "시이이X"],
        whitelist=["X바보"],
    )

    result = engine.check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == "시이이"
    assert result.matches[0].matched_text == "시이이"
    assert (result.matches[0].start, result.matches[0].end) == (0, 3)
    assert result.matches[0].method is MatchMethod.EXACT


def test_global_whitelist_falls_back_to_shorter_whitespace_candidate() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    text = "a b c-cd"
    engine = make_engine(
        blacklist=["ab", "abc"],
        whitelist=["ccd"],
        config=config,
    )

    result = engine.check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == "ab"
    assert result.matches[0].matched_text == "a b"
    assert (result.matches[0].start, result.matches[0].end) == (0, 3)
    assert result.matches[0].method is MatchMethod.WHITESPACE


def test_engine_bounds_overlapping_whitelist_mapping_and_reuses_view_mask() -> None:
    text = "a" * 512
    engine = make_engine(
        blacklist=["a"],
        whitelist=["a" * size for size in range(2, 130)],
    )

    with patch.object(
        matcher_module,
        "_map_candidate",
        wraps=matcher_module._map_candidate,
    ) as map_candidate:
        result = engine.check(text)

    assert result.detected is False
    assert result.matches == ()
    maximum_blacklist_candidates = len(text)
    maximum_whitelist_union_candidates = len(text)
    assert map_candidate.call_count <= (
        maximum_blacklist_candidates + maximum_whitelist_union_candidates
    )


def test_unconfigured_separator_does_not_trigger_obfuscation_view() -> None:
    config = EngineConfig(obfuscation_separators=frozenset({"*"}))
    engine = make_engine(blacklist=["시발"], config=config)

    assert engine.check("시/발").detected is False


def test_compatibility_separator_setting_matches_normalized_input() -> None:
    config = EngineConfig(obfuscation_separators=frozenset({"＊"}))
    engine = make_engine(blacklist=["시발"], config=config)

    result = engine.check("시＊발")

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == "시＊발"
    assert result.matches[0].method is MatchMethod.SEPARATOR


def test_whitespace_gap_matching_is_opt_in() -> None:
    engine = make_engine(blacklist=["시발"])

    assert engine.check("시 발").detected is False


def test_whitespace_gap_matching_detects_term_with_original_span() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(blacklist=["시발"], config=config)
    text = "이런 시 발 표현"

    result = engine.check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == "시 발"
    assert (result.matches[0].start, result.matches[0].end) == (3, 6)
    assert result.matches[0].method is MatchMethod.WHITESPACE


@pytest.mark.parametrize(
    "blacklist,text",
    [
        (["시발"], "시 발표"),
        (["시발"], "도시 발"),
        (["개새끼"], "개 새끼손가락"),
    ],
)
def test_whitespace_gap_matching_rejects_partial_alphanumeric_tokens(
    blacklist: list[str],
    text: str,
) -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(blacklist=blacklist, config=config)

    assert engine.check(text).detected is False


def test_whitespace_gap_matching_respects_gap_limit_and_rejects_line_breaks() -> None:
    config = EngineConfig(
        whitespace_gap_matching=True,
        max_whitespace_gap=2,
    )
    engine = make_engine(blacklist=["시발"], config=config)

    assert engine.check("시\t\t발").detected is True
    assert engine.check("시   발").detected is False
    assert engine.check("시\n발").detected is False


def test_exact_and_whitespace_gap_matches_are_both_preserved() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(blacklist=["병신", "시발"], config=config)

    result = engine.check("병신 그리고 시 발")

    assert [(match.term, match.method) for match in result.matches] == [
        ("병신", MatchMethod.EXACT),
        ("시발", MatchMethod.WHITESPACE),
    ]


def test_whitespace_gap_matching_does_not_expand_whitelist_spacing() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["시발"],
        whitelist=["시발 자동차"],
        config=config,
    )

    result = engine.check("시 발 자동차")

    assert [match.term for match in result.matches] == ["시발"]


@pytest.mark.parametrize(
    ("blacklist", "text", "expected_term"),
    [
        (["시발"], "시 * 발", "시발"),
        (["시발"], "시\t-*발", "시발"),
        (["시발"], "시\t*\t발", "시발"),
        (["개새끼"], "개 * 새 * 끼", "개새끼"),
    ],
)
def test_mixed_gap_matching_detects_whitespace_and_configured_separators(
    blacklist: list[str],
    text: str,
    expected_term: str,
) -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(blacklist=blacklist, config=config)

    result = engine.check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == expected_term
    assert result.matches[0].matched_text == text
    assert (result.matches[0].start, result.matches[0].end) == (0, len(text))
    assert result.matches[0].method is MatchMethod.MIXED


def test_mixed_gap_matching_is_opt_in() -> None:
    engine = make_engine(blacklist=["시발"])

    assert engine.check("시 * 발").detected is False


@pytest.mark.parametrize(
    ("blacklist", "text"),
    [
        (["시발"], "시 * 발표"),
        (["시발"], "도시 * 발"),
        (["개새끼"], "개 * 새끼손가락"),
        (["시발"], "시 / 발"),
        (["시발"], "시\n*발"),
        (["시발"], "시*\n발"),
        (["시발"], "시\u00a0*발"),
        (["시발"], "시   *발"),
        (["시발"], "시 *   발"),
    ],
)
def test_mixed_gap_matching_rejects_invalid_gaps_and_partial_tokens(
    blacklist: list[str],
    text: str,
) -> None:
    config = EngineConfig(
        whitespace_gap_matching=True,
        max_whitespace_gap=2,
        obfuscation_separators=frozenset({"*"}),
    )
    engine = make_engine(blacklist=blacklist, config=config)

    assert engine.check(text).detected is False


@pytest.mark.parametrize(
    "extension",
    ["\u0301", "\u034f", "\u20dd", "\ufe0f", "\U000e0100"],
)
@pytest.mark.parametrize("text_template", ["도{}시 * 발", "시 * 발{}표"])
def test_mixed_gap_matching_rejects_cluster_extended_partial_tokens(
    extension: str,
    text_template: str,
) -> None:
    config = EngineConfig(
        whitespace_gap_matching=True,
        obfuscation_separators=frozenset({"*"}),
    )
    engine = make_engine(blacklist=["시발"], config=config)

    assert engine.check(text_template.format(extension)).detected is False


@pytest.mark.parametrize("extension", ["\u0301", "\u034f", "\ufe0f"])
@pytest.mark.parametrize("text_template", ["!{}시 * 발", "시 * 발{}!"])
def test_mixed_gap_matching_accepts_cluster_extensions_next_to_punctuation(
    extension: str,
    text_template: str,
) -> None:
    config = EngineConfig(
        whitespace_gap_matching=True,
        obfuscation_separators=frozenset({"*"}),
    )
    engine = make_engine(blacklist=["시발"], config=config)

    result = engine.check(text_template.format(extension))

    assert [(match.term, match.method) for match in result.matches] == [("시발", MatchMethod.MIXED)]


@pytest.mark.parametrize(
    "extension",
    ["\u0301", "\u034f", "\u20dd", "\ufe0f", "\U000e0100"],
)
@pytest.mark.parametrize("text_template", ["도{}시 발", "시 발{}표"])
def test_whitespace_gap_matching_rejects_cluster_extended_partial_tokens(
    extension: str,
    text_template: str,
) -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(blacklist=["시발"], config=config)

    assert engine.check(text_template.format(extension)).detected is False


def test_mixed_gap_matching_does_not_expand_whitelist_obfuscation() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["시발"],
        whitelist=["시발 자동차"],
        config=config,
    )

    result = engine.check("시 * 발 자동차")

    assert [match.term for match in result.matches] == ["시발"]
    assert result.matches[0].method is MatchMethod.MIXED


def test_exact_whitelist_span_protects_mixed_gap_match() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["시발", "병신"],
        whitelist=["시 * 발"],
        config=config,
    )

    result = engine.check("시 * 발 그리고 병 * 신")

    assert [match.term for match in result.matches] == ["병신"]
    assert result.matches[0].method is MatchMethod.MIXED


def test_global_whitelist_falls_back_to_shorter_mixed_candidate() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["ab", "abc"],
        whitelist=["ccd"],
        config=config,
    )

    result = engine.check("a * b * c-cd")

    assert len(result.matches) == 1
    assert result.matches[0].term == "ab"
    assert result.matches[0].matched_text == "a * b"
    assert (result.matches[0].start, result.matches[0].end) == (0, 5)
    assert result.matches[0].method is MatchMethod.MIXED


def test_mixed_gap_matching_falls_back_when_longest_candidate_has_no_token_boundary() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["ab", "abc"],
        config=config,
    )

    result = engine.check("a * b-cd")

    assert len(result.matches) == 1
    assert result.matches[0].term == "ab"
    assert result.matches[0].matched_text == "a * b"
    assert (result.matches[0].start, result.matches[0].end) == (0, 5)
    assert result.matches[0].method is MatchMethod.MIXED


def test_mixed_gap_matching_falls_back_across_nonterminal_boundary() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["ab", "abcd"],
        config=config,
    )

    result = engine.check("a * b c * dX")

    assert [(match.term, match.matched_text, match.method) for match in result.matches] == [
        ("ab", "a * b", MatchMethod.MIXED)
    ]


def test_exact_priority_does_not_hide_non_overlapping_mixed_fallback() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["ab", "abcde", "defg"],
        config=config,
    )

    result = engine.check("ab * c d * e f*g")

    assert [
        (match.term, match.matched_text, match.start, match.end, match.method)
        for match in result.matches
    ] == [
        ("ab", "ab", 0, 2, MatchMethod.EXACT),
        ("defg", "d * e f*g", 7, 16, MatchMethod.MIXED),
    ]


def test_mixed_gap_matching_keeps_shorter_candidate_after_longer_overlap() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["ab", "abcdef", "defghijk"],
        config=config,
    )
    text = "a * b c * d e * f g * h i * j k"

    first = engine.check(text)
    second = engine.check(text)

    assert [(match.term, match.method) for match in first.matches] == [
        ("ab", MatchMethod.MIXED),
        ("defghijk", MatchMethod.MIXED),
    ]
    assert second.matches == first.matches


def test_mixed_gap_matching_bounds_deep_shared_prefix_work() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["a" * length for length in range(2, 258)],
        config=config,
    )
    text = "a * " * 1_024

    with patch.object(
        matcher_module,
        "_map_candidate",
        wraps=matcher_module._map_candidate,
    ) as map_candidate:
        result = engine.check(text)

    assert len(text) == config.max_input_length
    assert [len(match.term) for match in result.matches] == [257, 257, 257, 253]
    assert [(match.start, match.end) for match in result.matches] == [
        (0, 1_025),
        (1_028, 2_053),
        (2_056, 3_081),
        (3_084, 4_093),
    ]
    assert all(match.method is MatchMethod.MIXED for match in result.matches)
    assert map_candidate.call_count <= len(text)


def test_whitespace_gap_matching_bounds_deep_shared_prefix_work() -> None:
    config = EngineConfig(whitespace_gap_matching=True)
    engine = make_engine(
        blacklist=["a" * length for length in range(2, 258)],
        config=config,
    )
    text = ("a " * 2_048)[:4_095] + "a"

    with patch.object(
        matcher_module,
        "_map_candidate",
        wraps=matcher_module._map_candidate,
    ) as map_candidate:
        result = engine.check(text)

    assert len(text) == config.max_input_length
    assert len(result.matches) == 8
    assert map_candidate.call_count <= len(text)


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
