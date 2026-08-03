"""Unit tests for low-cost exact matching."""

from typing import SupportsIndex
from unittest.mock import patch

import pytest

from koguard import KoguardDictionary, MatchMethod
from koguard.engine import matcher as matcher_module
from koguard.engine.matcher import ExactMatcher
from koguard.engine.normalizer import NormalizedText, normalize_text


class ReadCountingText(str):
    """Count deterministic character reads performed by matching code."""

    read_count: int

    def __getitem__(self, key: SupportsIndex | slice, /) -> str:
        if not isinstance(key, slice):
            self.read_count += 1
        return super().__getitem__(key)


def make_matcher(
    *,
    blacklist: list[str],
    whitelist: list[str] | None = None,
) -> ExactMatcher:
    dictionary = KoguardDictionary.from_sources(
        blacklist=blacklist,
        whitelist=whitelist or [],
        include_defaults=False,
    )
    return ExactMatcher(dictionary)


def test_exact_matcher_prefers_longest_shared_prefix_and_keeps_later_match() -> None:
    matcher = make_matcher(blacklist=["금", "금칙", "욕설"])
    text = "금칙 그리고 욕설"

    matches = matcher.find(text, normalize_text(text, "NFKC"))

    assert [match.term for match in matches] == ["금칙", "욕설"]
    assert [match.matched_text for match in matches] == ["금칙", "욕설"]


def test_exact_matcher_applies_whitelist_to_only_overlapping_span() -> None:
    matcher = make_matcher(
        blacklist=["시발", "병신"],
        whitelist=["시발점"],
    )
    text = "시발점과 병신"

    matches = matcher.find(text, normalize_text(text, "NFKC"))

    assert [match.term for match in matches] == ["병신"]


def test_exact_matcher_selects_non_overlapping_longest_matches_from_many_candidates() -> None:
    matcher = make_matcher(
        blacklist=["a" * size for size in range(1, 9)],
        whitelist=["정상"],
    )

    matches = matcher.find("a" * 64, normalize_text("a" * 64, "NFKC"))

    assert len(matches) == 8
    assert all(match.term == "a" * 8 for match in matches)


def test_exact_matcher_bounds_candidates_and_keeps_deterministic_results() -> None:
    text = "a" * 512
    matcher = make_matcher(
        blacklist=["a" * size for size in range(2, 130)],
    )
    normalized = normalize_text(text, "NFKC")

    with patch.object(
        matcher_module,
        "_map_candidate",
        wraps=matcher_module._map_candidate,
    ) as map_candidate:
        first = matcher.find(text, normalized)
        first_candidate_count = map_candidate.call_count
        map_candidate.reset_mock()
        second = matcher.find(text, normalized)
        second_candidate_count = map_candidate.call_count

    expected = [
        (129, 0, 129),
        (129, 129, 258),
        (129, 258, 387),
        (125, 387, 512),
    ]
    assert [(len(match.term), match.start, match.end) for match in first] == expected
    assert second == first
    assert first_candidate_count <= len(text) * 4
    assert second_candidate_count == first_candidate_count


def test_exact_matcher_skips_starts_too_short_for_single_long_term() -> None:
    term = "a" * 4_096
    counted_text = ReadCountingText(term)
    counted_text.read_count = 0
    matcher = make_matcher(blacklist=[term])
    normalized = NormalizedText(
        text=counted_text,
        source_spans=tuple((index, index + 1) for index in range(len(term))),
    )

    matches = matcher.find(term, normalized)

    assert len(matches) == 1
    assert matches[0].term == term
    assert matches[0].matched_text == term
    assert (matches[0].start, matches[0].end) == (0, len(term))
    assert matches[0].method is MatchMethod.EXACT
    assert counted_text.read_count <= len(term)


def test_exact_matcher_bounds_character_reads_with_short_and_long_term() -> None:
    text = "a" * 4_096
    counted_text = ReadCountingText(text)
    counted_text.read_count = 0
    normalized = NormalizedText(
        text=counted_text,
        source_spans=tuple((index, index + 1) for index in range(len(text))),
    )
    matcher = make_matcher(blacklist=["a", text])

    matches = matcher.find(text, normalized)

    assert len(matches) == 1
    assert matches[0].term == text
    assert matches[0].matched_text == text
    assert (matches[0].start, matches[0].end) == (0, len(text))
    assert matches[0].method is MatchMethod.EXACT
    assert counted_text.read_count <= len(text) * 4


def test_exact_matcher_bounds_character_reads_with_dense_prefix_terms() -> None:
    text = "a" * 512
    counted_text = ReadCountingText(text)
    counted_text.read_count = 0
    normalized = NormalizedText(
        text=counted_text,
        source_spans=tuple((index, index + 1) for index in range(len(text))),
    )
    matcher = make_matcher(
        blacklist=["a" * size for size in range(1, len(text) + 1)],
    )

    matches = matcher.find(text, normalized)

    assert len(matches) == 1
    assert matches[0].term == text
    assert matches[0].matched_text == text
    assert (matches[0].start, matches[0].end) == (0, len(text))
    assert matches[0].method is MatchMethod.EXACT
    assert counted_text.read_count <= len(text) * 8


def test_whitespace_gap_matcher_returns_full_original_span() -> None:
    matcher = make_matcher(blacklist=["시발"])
    text = "이런 시\t\t발 표현"

    matches = matcher.find_with_whitespace_gaps(
        text,
        normalize_text(text, "NFKC"),
        max_whitespace_gap=2,
    )

    assert len(matches) == 1
    assert matches[0].term == "시발"
    assert matches[0].matched_text == "시\t\t발"
    assert (matches[0].start, matches[0].end) == (3, 7)
    assert matches[0].method is MatchMethod.WHITESPACE


@pytest.mark.parametrize("text", ["시 발표", "도시 발"])
def test_whitespace_gap_matcher_rejects_partial_alphanumeric_tokens(text: str) -> None:
    matcher = make_matcher(blacklist=["시발"])

    matches = matcher.find_with_whitespace_gaps(
        text,
        normalize_text(text, "NFKC"),
        max_whitespace_gap=3,
    )

    assert matches == ()


def test_whitespace_gap_matcher_rejects_gap_over_limit_and_line_breaks() -> None:
    matcher = make_matcher(blacklist=["시발"])

    too_wide = matcher.find_with_whitespace_gaps(
        "시   발",
        normalize_text("시   발", "NFKC"),
        max_whitespace_gap=2,
    )
    line_break = matcher.find_with_whitespace_gaps(
        "시\n발",
        normalize_text("시\n발", "NFKC"),
        max_whitespace_gap=3,
    )

    assert too_wide == ()
    assert line_break == ()


def test_whitespace_gap_matcher_applies_whitelist_to_only_overlapping_span() -> None:
    matcher = make_matcher(
        blacklist=["시발", "병신"],
        whitelist=["시 발"],
    )
    text = "시 발 그리고 병 신"

    matches = matcher.find_with_whitespace_gaps(
        text,
        normalize_text(text, "NFKC"),
        max_whitespace_gap=3,
    )

    assert [match.term for match in matches] == ["병신"]


def test_whitespace_gap_matcher_keeps_shorter_candidate_after_longer_overlap() -> None:
    matcher = make_matcher(
        blacklist=["ab", "abcdef", "defghijk"],
    )
    text = "a b c d e f g h i j k"

    matches = matcher.find_with_whitespace_gaps(
        text,
        normalize_text(text, "NFKC"),
        max_whitespace_gap=1,
    )

    assert [match.term for match in matches] == ["ab", "defghijk"]


def test_whitespace_gap_matcher_keeps_shorter_candidate_before_whitelist_span() -> None:
    matcher = make_matcher(
        blacklist=["ab", "abc"],
        whitelist=["c"],
    )
    text = "a b c"

    matches = matcher.find_with_whitespace_gaps(
        text,
        normalize_text(text, "NFKC"),
        max_whitespace_gap=1,
    )

    assert [match.term for match in matches] == ["ab"]


def test_mixed_gap_matcher_returns_full_original_span() -> None:
    matcher = make_matcher(blacklist=["시발"])
    text = "이런 시\t-*발 표현"

    matches = matcher.find_with_mixed_gaps(
        text,
        normalize_text(text, "NFKC"),
        max_whitespace_gap=1,
        separators=frozenset({"-", "*"}),
    )

    assert len(matches) == 1
    assert matches[0].term == "시발"
    assert matches[0].matched_text == "시\t-*발"
    assert (matches[0].start, matches[0].end) == (3, 8)
    assert matches[0].method is MatchMethod.MIXED


def test_mixed_gap_matcher_reads_maximum_input_a_bounded_number_of_times() -> None:
    text = "a * " * 1_024
    counted_text = ReadCountingText(text)
    counted_text.read_count = 0
    normalized = NormalizedText(
        text=counted_text,
        source_spans=tuple((index, index + 1) for index in range(len(text))),
    )
    matcher = make_matcher(
        blacklist=["a" * length for length in range(2, 258)],
    )

    matches = matcher.find_with_mixed_gaps(
        text,
        normalized,
        max_whitespace_gap=1,
        separators=frozenset({"*"}),
    )

    assert [len(match.term) for match in matches] == [257, 257, 257, 253]
    assert counted_text.read_count <= len(text) * 2


def test_mixed_gap_matcher_skips_impossible_shared_prefix_fallbacks() -> None:
    text = "a * " + ("a" * 4_092)
    matcher = make_matcher(
        blacklist=["a" * length for length in range(2, 258)],
    )

    with patch.object(
        matcher_module,
        "_next_shorter_occurrence",
        wraps=matcher_module._next_shorter_occurrence,
    ) as next_shorter:
        matches = matcher.find_with_mixed_gaps(
            text,
            normalize_text(text, "NFKC"),
            max_whitespace_gap=1,
            separators=frozenset({"*"}),
        )

    assert len(text) == 4_096
    assert matches == ()
    assert next_shorter.call_count <= len(text)


def test_mixed_gap_matcher_bounds_fallbacks_before_alphanumeric_suffix() -> None:
    text = ("a * " * 128) + ("a" * 512)
    matcher = make_matcher(
        blacklist=["a" * length for length in range(2, 160)],
    )

    with patch.object(
        matcher_module,
        "_next_shorter_occurrence",
        wraps=matcher_module._next_shorter_occurrence,
    ) as next_shorter:
        matches = matcher.find_with_mixed_gaps(
            text,
            normalize_text(text, "NFKC"),
            max_whitespace_gap=1,
            separators=frozenset({"*"}),
        )

    assert len(text) == 1_024
    assert [(len(match.term), match.start, match.end) for match in matches] == [(128, 0, 509)]
    assert next_shorter.call_count <= len(text)
