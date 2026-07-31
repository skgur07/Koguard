"""Tests for public match result models."""

from typing import cast

import pytest

from koguard import CheckResult, Match, MatchMethod


def make_match() -> Match:
    return Match(
        term="금칙어",
        matched_text="금칙어",
        start=2,
        end=5,
        method=MatchMethod.EXACT,
        score=1.0,
    )


def test_mixed_match_method_has_stable_public_value() -> None:
    assert MatchMethod.MIXED.value == "mixed"


def test_detected_result_exposes_first_match_compatibility_properties() -> None:
    match = make_match()
    result = CheckResult(normalized_text="문장금칙어", matches=(match,), elapsed_ms=0.25)

    assert result.detected is True
    assert result.matched_word == "금칙어"
    assert result.method is MatchMethod.EXACT
    assert result.confidence == 1.0


def test_clean_result_uses_empty_defaults() -> None:
    result = CheckResult(normalized_text="정상 문장")

    assert result.detected is False
    assert result.matches == ()
    assert result.matched_word is None
    assert result.method is MatchMethod.NONE
    assert result.confidence == 0.0


def test_result_copies_mutable_match_collections() -> None:
    match = make_match()
    source = [match]
    result = CheckResult(
        normalized_text="금칙어",
        matches=cast(tuple[Match, ...], source),
    )

    source.clear()

    assert result.matches == (match,)
    assert result.detected is True


def test_result_rejects_non_match_items() -> None:
    invalid_matches = cast(tuple[Match, ...], ("not-a-match",))

    with pytest.raises(TypeError, match="Match instances"):
        CheckResult(normalized_text="", matches=invalid_matches)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (0, None),
        (None, 1),
        (-1, 1),
        (1, 1),
        (2, 1),
    ],
)
def test_match_rejects_invalid_spans(start: int | None, end: int | None) -> None:
    with pytest.raises(ValueError, match="start|span"):
        Match(
            term="금칙어",
            matched_text="금칙어",
            start=start,
            end=end,
            method=MatchMethod.EXACT,
            score=1.0,
        )


@pytest.mark.parametrize("field", ["term", "matched_text"])
def test_match_rejects_empty_text_fields(field: str) -> None:
    values = {
        "term": "금칙어",
        "matched_text": "금칙어",
    }
    values[field] = ""

    with pytest.raises(ValueError, match=field):
        Match(
            term=values["term"],
            matched_text=values["matched_text"],
            start=None,
            end=None,
            method=MatchMethod.EMBEDDING,
            score=0.8,
        )


@pytest.mark.parametrize("score", [-0.01, 1.01, float("nan")])
def test_match_rejects_invalid_scores(score: float) -> None:
    with pytest.raises(ValueError, match="score"):
        Match(
            term="금칙어",
            matched_text="금칙어",
            start=None,
            end=None,
            method=MatchMethod.EMBEDDING,
            score=score,
        )


def test_match_rejects_none_method() -> None:
    with pytest.raises(ValueError, match="NONE"):
        Match(
            term="금칙어",
            matched_text="금칙어",
            start=0,
            end=3,
            method=MatchMethod.NONE,
            score=1.0,
        )


@pytest.mark.parametrize("elapsed_ms", [-0.01, float("nan"), float("inf")])
def test_result_rejects_invalid_elapsed_time(elapsed_ms: float) -> None:
    with pytest.raises(ValueError, match="elapsed_ms"):
        CheckResult(normalized_text="", elapsed_ms=elapsed_ms)
