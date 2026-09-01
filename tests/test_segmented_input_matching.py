"""Integration tests for bounded gaps inside choseong, jamo, and keyboard input."""

import pytest

from koguard import (
    EngineConfig,
    KoguardDictionary,
    KoguardEngine,
    MatchMethod,
    NormalizationForm,
)


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
        ("ㅅ ㅂ", MatchMethod.CHOSEONG),
        ("ㅅ*ㅂ", MatchMethod.CHOSEONG),
        ("ㅅ * ㅂ", MatchMethod.CHOSEONG),
        ("ㅅㅣ ㅂㅏㄹ", MatchMethod.JAMO),
        ("ㅅㅣ*ㅂㅏㄹ", MatchMethod.JAMO),
        ("tl * qkf", MatchMethod.KEYBOARD),
        ("tl*qkf", MatchMethod.KEYBOARD),
    ],
)
def test_segmented_input_detects_profanity_with_original_span(
    text: str,
    method: MatchMethod,
) -> None:
    result = make_engine().check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == text
    assert (result.matches[0].start, result.matches[0].end) == (0, len(text))
    assert result.matches[0].method is method


def test_segmented_choseong_allows_korean_particle_suffix() -> None:
    text = "ㅅ ㅂ이"

    result = make_engine().check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == "시발"
    assert result.matches[0].matched_text == "ㅅ ㅂ"
    assert (result.matches[0].start, result.matches[0].end) == (0, 3)
    assert result.matches[0].method is MatchMethod.CHOSEONG


@pytest.mark.parametrize("text", ["ㅅ ㅂ", "ㅅ*ㅂ", "ㅅㅣ ㅂㅏㄹ", "tl * qkf"])
def test_segmented_input_matching_can_be_disabled(text: str) -> None:
    engine = make_engine(config=EngineConfig(segmented_input_matching=False))

    assert engine.check(text).detected is False


@pytest.mark.parametrize(
    ("text", "config"),
    [
        ("ㅅ ㅂ", EngineConfig(choseong_matching=False)),
        ("ㅅㅣ ㅂㅏㄹ", EngineConfig(jamo_composition_matching=False)),
        ("tl * qkf", EngineConfig(keyboard_matching=False)),
    ],
)
def test_segmented_input_respects_base_matcher_flags(text: str, config: EngineConfig) -> None:
    assert make_engine(config=config).check(text).detected is False


def test_segmented_choseong_does_not_require_jamo_composition_matching() -> None:
    config = EngineConfig(
        choseong_matching=True,
        jamo_composition_matching=False,
        segmented_input_matching=True,
    )

    result = make_engine(config=config).check("ㅅ ㅂ")

    assert result.detected is True
    assert result.method is MatchMethod.CHOSEONG


@pytest.mark.parametrize("unicode_form", ["NFC", "NFKC"])
def test_segmented_choseong_supports_configured_unicode_form(
    unicode_form: NormalizationForm,
) -> None:
    config = EngineConfig(unicode_form=unicode_form)

    result = make_engine(config=config).check("ㅅ ㅂ")

    assert result.detected is True
    assert result.method is MatchMethod.CHOSEONG
    assert result.matches[0].matched_text == "ㅅ ㅂ"
    assert (result.matches[0].start, result.matches[0].end) == (0, 3)


@pytest.mark.parametrize(
    "text",
    ["시 발표", "3시 발표", "ㅅ 발표", "aㅅ ㅂ", "ㅅ ㅂ1", "ㅅ ㅂㄹ", "tl * abc"],
)
def test_segmented_input_does_not_join_partial_or_unrelated_tokens(text: str) -> None:
    assert make_engine().check(text).detected is False


@pytest.mark.parametrize(
    "text",
    ["ㅅ/ㅂ", "ㅅㅣ/ㅂㅏㄹ", "tl/qkf", "ㅅ    ㅂ", "ㅅ\nㅂ", "ㅅㅣ    ㅂㅏㄹ", "tl\nqkf"],
)
def test_segmented_input_rejects_unconfigured_or_invalid_gaps(text: str) -> None:
    config = EngineConfig(
        obfuscation_separators=frozenset({"*"}),
        max_whitespace_gap=3,
    )

    assert make_engine(config=config).check(text).detected is False


@pytest.mark.parametrize(
    ("text", "whitelist"),
    [
        ("ㅅ * ㅂ", ["ㅅㅂ"]),
        ("ㅅㅣ * ㅂㅏㄹㅈㅓㅁ", ["시발점"]),
        ("tl * qkfwja", ["시발점"]),
    ],
)
def test_segmented_input_honors_transformed_whitelist(
    text: str,
    whitelist: list[str],
) -> None:
    assert make_engine(whitelist=whitelist).check(text).detected is False


@pytest.mark.parametrize(
    ("continuous", "segmented"),
    [
        ("ㅅㅂ", "ㅅ ㅂ"),
        ("ㅅㅣㅂㅏㄹ", "ㅅㅣ ㅂㅏㄹ"),
        ("tlqkf", "tl * qkf"),
    ],
)
def test_disabling_segmented_input_keeps_continuous_views(
    continuous: str,
    segmented: str,
) -> None:
    engine = make_engine(config=EngineConfig(segmented_input_matching=False))

    assert engine.check(continuous).detected is True
    assert engine.check(segmented).detected is False
