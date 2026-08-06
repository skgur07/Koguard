"""Integration tests for keyboard and compatibility-jamo input views."""

import pytest

from koguard import EngineConfig, KoguardDictionary, KoguardEngine, MatchMethod


def make_engine(
    *,
    config: EngineConfig | None = None,
    whitelist: list[str] | None = None,
) -> KoguardEngine:
    resolved_config = config or EngineConfig()
    dictionary = KoguardDictionary.from_sources(
        blacklist=["시발"],
        whitelist=whitelist or [],
        include_defaults=False,
        unicode_form=resolved_config.unicode_form,
    )
    return KoguardEngine(config=resolved_config, dictionary=dictionary)


@pytest.mark.parametrize(
    ("text", "method"),
    [
        ("tlqkf", MatchMethod.KEYBOARD),
        ("ㅅㅣㅂㅏㄹ", MatchMethod.JAMO),
    ],
)
def test_composed_input_views_detect_profanity_with_original_span(
    text: str,
    method: MatchMethod,
) -> None:
    result = make_engine().check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == text
    assert (result.matches[0].start, result.matches[0].end) == (0, len(text))
    assert result.matches[0].method is method
    assert result.matches[0].score == 1.0
    assert result.normalized_text == (text if text == "tlqkf" else "시바ᄅ")


def test_keyboard_matching_can_be_disabled_independently() -> None:
    result = make_engine(config=EngineConfig(keyboard_matching=False)).check("tlqkf")

    assert result.detected is False


def test_jamo_composition_matching_can_be_disabled_independently() -> None:
    result = make_engine(config=EngineConfig(jamo_composition_matching=False)).check("ㅅㅣㅂㅏㄹ")

    assert result.detected is False


@pytest.mark.parametrize(
    "text",
    [
        "tlqkfwja",
        "ㅅㅣㅂㅏㄹㅈㅓㅁ",
    ],
)
def test_composed_input_views_honor_transformed_whitelist(text: str) -> None:
    result = make_engine(whitelist=["시발점"]).check(text)

    assert result.detected is False


@pytest.mark.parametrize("text", ["hello", "3tlq"])
def test_composed_input_views_do_not_join_unrelated_input(text: str) -> None:
    assert make_engine().check(text).detected is False
