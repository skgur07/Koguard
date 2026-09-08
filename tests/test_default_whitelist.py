"""What the bundled whitelist protects, and what it deliberately does not.

Some dictionary terms are written exactly like ordinary Korean. Where the two
senses are separated by a closed set of following words -- an auxiliary verb, a
connective ending, a compound's second root -- that set can be enumerated, and
the bundled whitelist enumerates it.

Where the following words form an open set, no whitelist entry can help. Those
cases are asserted here as known false positives rather than left unstated, so
that a later fix has a test to flip instead of a gap to discover.

The whitelist protects only the overlapping span, never the whole result, so
these cases also check that real profanity in the same shape still lands.
"""

import pytest

from koguard import KoguardEngine


@pytest.fixture(scope="module")
def engine() -> KoguardEngine:
    return KoguardEngine()


@pytest.mark.parametrize(
    "text",
    [
        "전원이 꺼져 있었다",
        "불이 꺼져 버렸다",
        "촛불이 꺼져 가는 중이다",
        "전등이 꺼져서 어두웠다",
        "위기가 닥쳐올 것이다",
        "위기가 닥쳐온 뒤였다",
        "마감이 닥쳐서 서둘렀다",
        "서랍을 뒤져 보았다",
        "온 집을 뒤져도 없었다",
        "가방을 뒤져서 찾았다",
        "등신대 모형을 세웠다",
        "절에서 등신불을 보았다",
        "영화를 보지 못했어",
        "그것을 보지 않았다",
        "쳐다보지 말고 가자",
        "뒤돌아보지 마",
    ],
)
def test_ordinary_korean_with_a_closed_complement_set_is_protected(
    engine: KoguardEngine, text: str
) -> None:
    assert engine.contains(text) is False, text


@pytest.mark.parametrize(
    ("text", "expected_term"),
    [
        ("그만 꺼져", "꺼져"),
        ("닥쳐 아무 말도 하지 마", "닥쳐"),
        ("등신도 아니고", "등신"),
        ("이 보지야", "보지"),
        ("저 새끼 뭐야", "새끼"),
    ],
)
def test_the_whitelist_does_not_shield_the_profane_reading(
    engine: KoguardEngine, text: str, expected_term: str
) -> None:
    result = engine.check(text)

    assert result.detected is True, text
    assert expected_term in [match.term for match in result.matches]


@pytest.mark.parametrize(
    "text",
    [
        "촛불이 바람에 꺼져 어두워졌다",
        "온 집을 뒤질 각오로 찾았다",
        "고양이가 새끼를 낳았다",
    ],
)
def test_an_open_complement_set_remains_a_known_false_positive(
    engine: KoguardEngine, text: str
) -> None:
    """No whitelist entry can close these.

    `꺼져` takes any following verb phrase, adnominal `뒤질` any noun, and `새끼`
    the same particles as its profane reading. Separating them needs the term out
    of the default dictionary, which is a policy decision recorded in
    `docs/accuracy-baseline.md` rather than a change made here.
    """

    assert engine.contains(text) is True, f"{text} unexpectedly fixed; update the record"
