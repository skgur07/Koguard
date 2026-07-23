"""Tests for public match result models."""

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


def test_result_rejects_negative_elapsed_time() -> None:
    with pytest.raises(ValueError, match="elapsed_ms"):
        CheckResult(normalized_text="", elapsed_ms=-0.01)
