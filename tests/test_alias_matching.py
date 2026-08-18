"""Integration tests for explicit profanity alias matching."""

from unittest.mock import patch

import pytest

from koguard import (
    AliasMode,
    AliasRule,
    EngineConfig,
    KoguardDictionary,
    KoguardEngine,
    MatchMethod,
)
from koguard.engine import matcher as matcher_module

_ALIAS_RULES = (
    AliasRule("ㅈ같", "좆같다", AliasMode.TOKEN_PREFIX),
    AliasRule("ㅈ됐", "좆되다", AliasMode.TOKEN_PREFIX),
    AliasRule("ㅄ", "병신", AliasMode.EXACT_TOKEN),
    AliasRule("ㅈㄲ", "좆", AliasMode.EXACT_TOKEN),
    AliasRule("ㅅㅄㄲ", "시발새끼", AliasMode.EXACT_TOKEN),
)
_CANONICAL_TERMS = [rule.term for rule in _ALIAS_RULES]


def make_alias_engine(
    *,
    config: EngineConfig | None = None,
    whitelist: list[str] | None = None,
) -> KoguardEngine:
    resolved_config = config or EngineConfig()
    dictionary = KoguardDictionary.from_sources(
        blacklist=_CANONICAL_TERMS,
        whitelist=whitelist or [],
        aliases=_ALIAS_RULES,
        include_defaults=False,
        unicode_form=resolved_config.unicode_form,
    )
    return KoguardEngine(config=resolved_config, dictionary=dictionary)


@pytest.mark.parametrize(
    ("text", "term", "matched_text", "span"),
    [
        ("ㅈ같네", "좆같다", "ㅈ같", (0, 2)),
        ("ㅈ같은 상황", "좆같다", "ㅈ같", (0, 2)),
        ("ㅈ됐네", "좆되다", "ㅈ됐", (0, 2)),
        ("ㅄ", "병신", "ㅄ", (0, 1)),
        ("ㅈㄲ", "좆", "ㅈㄲ", (0, 2)),
        ("ㅅㅄㄲ", "시발새끼", "ㅅㅄㄲ", (0, 3)),
    ],
)
def test_alias_matching_detects_curated_forms_with_original_span(
    text: str,
    term: str,
    matched_text: str,
    span: tuple[int, int],
) -> None:
    result = make_alias_engine().check(text)

    assert len(result.matches) == 1
    assert result.matches[0].term == term
    assert result.matches[0].matched_text == matched_text
    assert (result.matches[0].start, result.matches[0].end) == span
    assert result.matches[0].method is MatchMethod.ALIAS
    assert result.matches[0].score == 1.0


def test_alias_matching_is_enabled_by_default_and_can_be_disabled() -> None:
    enabled_result = make_alias_engine().check("ㅈ같네")
    disabled_result = make_alias_engine(
        config=EngineConfig(alias_matching=False),
    ).check("ㅈ같네")

    assert enabled_result.detected is True
    assert disabled_result.detected is False


@pytest.mark.parametrize(
    "text",
    [
        "3시 발표",
        "시 발표",
        "수박",
        "ㅈ 같은 모양",
        "aㅈ같네",
        "ㅈ같1",
        "ㅈ같ㄴ",
        "ㅈ같네abc",
        "ㅄ1",
        "ㅈㄲㅋ",
        "ㅅㅄㄲ네",
    ],
)
def test_alias_matching_rejects_unlisted_or_partial_tokens(text: str) -> None:
    assert make_alias_engine().check(text).detected is False


def test_alias_matching_skips_boundary_work_without_alias_leading_character() -> None:
    engine = make_alias_engine(
        config=EngineConfig(
            exact_matching=False,
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=False,
            mixed_gap_matching=False,
            alias_matching=True,
            keyboard_matching=False,
            jamo_composition_matching=False,
            choseong_matching=False,
            segmented_input_matching=False,
            fuzzy_matching=False,
        )
    )

    with patch.object(matcher_module, "_build_alphanumeric_boundaries") as boundaries:
        result = engine.check("가나다라마바사아자차카타파하" * 256)

    assert result.detected is False
    boundaries.assert_not_called()


def test_alias_matching_accepts_token_prefix_before_punctuation() -> None:
    text = "와,ㅈ같네!"
    result = make_alias_engine().check(text)

    assert len(result.matches) == 1
    assert result.matches[0].matched_text == "ㅈ같"
    assert (result.matches[0].start, result.matches[0].end) == (2, 4)


def test_alias_matching_honors_only_overlapping_whitelist_span() -> None:
    text = "ㅈ같네, ㅄ"
    result = make_alias_engine(whitelist=["ㅈ같네"]).check(text)

    assert [match.term for match in result.matches] == ["병신"]
    assert [match.matched_text for match in result.matches] == ["ㅄ"]
    assert [(match.start, match.end) for match in result.matches] == [(5, 6)]


@pytest.mark.parametrize("unicode_form", ["NFC", "NFKC"])
def test_alias_matching_supports_configured_unicode_form(unicode_form: str) -> None:
    config = EngineConfig(unicode_form=unicode_form)  # type: ignore[arg-type]
    result = make_alias_engine(config=config).check("ㅄ")

    assert result.matched_word == "병신"
    assert result.matches[0].matched_text == "ㅄ"
    assert (result.matches[0].start, result.matches[0].end) == (0, 1)


def test_alias_matching_maps_nfkc_expansion_back_to_original_span() -> None:
    text = "ﬁ ㅄ"
    result = make_alias_engine().check(text)

    assert result.normalized_text == "fi ᄡ"
    assert result.matches[0].matched_text == "ㅄ"
    assert (result.matches[0].start, result.matches[0].end) == (2, 3)
