"""PF-008 RED tests for the public engine profile contract."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import fields
from typing import cast

import pytest

from koguard import (
    AliasMode,
    AliasRule,
    ConfigurationError,
    EngineConfig,
    KoguardDictionary,
    KoguardEngine,
)

ProfileName = str

_MATCHER_FIELDS = (
    "exact_matching",
    "alias_matching",
    "repeated_matching",
    "separator_matching",
    "whitespace_gap_matching",
    "mixed_gap_matching",
    "keyboard_matching",
    "jamo_composition_matching",
    "choseong_matching",
    "segmented_input_matching",
    "fuzzy_matching",
)

_EXPECTED_CONFIGS = {
    "strict": EngineConfig(
        exact_matching=True,
        alias_matching=True,
        repeated_matching=False,
        separator_matching=False,
        whitespace_gap_matching=False,
        mixed_gap_matching=False,
        keyboard_matching=False,
        jamo_composition_matching=False,
        choseong_matching=False,
        segmented_input_matching=False,
        fuzzy_matching=False,
    ),
    "balanced": EngineConfig(
        exact_matching=True,
        alias_matching=True,
        repeated_matching=False,
        separator_matching=False,
        whitespace_gap_matching=False,
        mixed_gap_matching=False,
        keyboard_matching=False,
        jamo_composition_matching=False,
        choseong_matching=True,
        segmented_input_matching=False,
        fuzzy_matching=False,
    ),
    "aggressive": EngineConfig(
        exact_matching=True,
        alias_matching=True,
        repeated_matching=True,
        separator_matching=True,
        whitespace_gap_matching=True,
        mixed_gap_matching=True,
        keyboard_matching=True,
        jamo_composition_matching=True,
        choseong_matching=True,
        segmented_input_matching=True,
        fuzzy_matching=True,
    ),
}


def _engine_factory() -> Callable[..., KoguardEngine]:
    """Permit RED calls against the future constructor without weakening source typing."""

    return cast(Callable[..., KoguardEngine], KoguardEngine)


def _make_dictionary() -> KoguardDictionary:
    return KoguardDictionary.from_sources(
        blacklist=["시발", "병신"],
        whitelist=[],
        aliases=[AliasRule("ㅄ", "병신", AliasMode.EXACT_TOKEN)],
        include_defaults=False,
    )


def _result_signature(engine: KoguardEngine, text: str) -> tuple[object, ...]:
    result = engine.check(text)
    return (result.detected, result.normalized_text, result.matches)


def test_profile_table_covers_every_matcher_flag_explicitly() -> None:
    """A newly added matcher must be placed in every profile intentionally."""

    actual_matcher_fields = {
        field.name for field in fields(EngineConfig) if field.name.endswith("_matching")
    }

    assert actual_matcher_fields == set(_MATCHER_FIELDS)


def test_direct_config_contract_remains_available() -> None:
    config = EngineConfig(fuzzy_matching=False, max_input_length=128)

    engine = KoguardEngine(config=config)

    assert engine.config is config


@pytest.mark.parametrize("profile", ["strict", "balanced", "aggressive"])
def test_profile_exposes_the_fully_resolved_immutable_config(profile: ProfileName) -> None:
    engine = _engine_factory()(profile=profile)

    assert engine.config == _EXPECTED_CONFIGS[profile]


def test_default_engine_resolves_to_balanced_profile() -> None:
    assert KoguardEngine().config == _EXPECTED_CONFIGS["balanced"]


def test_aggressive_preserves_the_pre_profile_all_enabled_configuration() -> None:
    assert _engine_factory()(profile="aggressive").config == EngineConfig()


def test_none_profile_is_equivalent_to_omitting_profile() -> None:
    assert _engine_factory()(profile=None).config == KoguardEngine().config


def test_profile_and_direct_config_are_mutually_exclusive() -> None:
    with pytest.raises(ConfigurationError, match="profile.*config"):
        _engine_factory()(profile="strict", config=EngineConfig())


@pytest.mark.parametrize("profile", ["", "BALANCED", "unknown", 1, True])
def test_invalid_profile_is_rejected_as_configuration_error(profile: object) -> None:
    with pytest.raises(ConfigurationError, match="strict.*balanced.*aggressive"):
        _engine_factory()(profile=profile)


@pytest.mark.parametrize("profile", ["strict", "balanced", "aggressive"])
def test_every_profile_preserves_context_independent_exact_and_alias_core(
    profile: ProfileName,
) -> None:
    engine = _engine_factory()(profile=profile, dictionary=_make_dictionary())

    result = engine.check("시발점과 ㅄ")

    assert [(match.term, match.matched_text) for match in result.matches] == [
        ("시발", "시발"),
        ("병신", "ㅄ"),
    ]


@pytest.mark.parametrize("profile", ["strict", "balanced", "aggressive"])
def test_every_profile_keeps_whitelist_as_the_only_core_suppression(
    profile: ProfileName,
) -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["금칙"],
        whitelist=["금칙어"],
        include_defaults=False,
    )
    engine = _engine_factory()(profile=profile, dictionary=dictionary)
    text = "금칙어와 금칙"

    result = engine.check(text)

    assert [(match.matched_text, match.start, match.end) for match in result.matches] == [
        ("금칙", text.rindex("금칙"), len(text)),
    ]


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("strict", (True, False, False)),
        ("balanced", (True, True, False)),
        ("aggressive", (True, True, True)),
    ],
)
def test_profile_scope_is_visible_through_public_detection_behavior(
    profile: ProfileName,
    expected: tuple[bool, bool, bool],
) -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["시발"],
        include_defaults=False,
    )
    engine = _engine_factory()(profile=profile, dictionary=dictionary)

    actual = tuple(engine.check(text).detected for text in ("시발", "ㅅㅂ", "시*!발"))

    assert actual == expected


@pytest.mark.parametrize(
    ("profile", "expected"),
    [
        ("strict", (False, False, False)),
        ("balanced", (False, False, True)),
        ("aggressive", (True, True, True)),
    ],
)
def test_profile_scope_preserves_korean_particle_suffix_behavior(
    profile: ProfileName,
    expected: tuple[bool, bool, bool],
) -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["시발"],
        include_defaults=False,
    )
    engine = _engine_factory()(profile=profile, dictionary=dictionary)

    actual = tuple(
        engine.check(text).detected
        for text in (
            "시  발은",
            "ㅅ ㅂ이",
            "ㅅㅂ이",
        )
    )

    assert actual == expected


@pytest.mark.parametrize("profile", ["strict", "balanced", "aggressive"])
def test_profile_results_are_deterministic(profile: ProfileName) -> None:
    engine = _engine_factory()(profile=profile, dictionary=_make_dictionary())
    text = "시발점과 ㅄ 그리고 ㅅㅂ"

    signatures = [_result_signature(engine, text) for _ in range(20)]

    assert signatures == [signatures[0]] * len(signatures)


@pytest.mark.parametrize("profile", ["strict", "balanced", "aggressive"])
def test_profile_engine_is_safe_for_concurrent_checks(profile: ProfileName) -> None:
    engine = _engine_factory()(profile=profile, dictionary=_make_dictionary())
    texts = ["정상 문장", "시발점", "ㅄ", "ㅅㅂ"] * 10
    expected = [_result_signature(engine, text) for text in texts]

    with ThreadPoolExecutor(max_workers=4) as executor:
        actual = list(executor.map(lambda text: _result_signature(engine, text), texts))

    assert actual == expected
