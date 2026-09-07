"""Preset configurations and the contextual dictionary tier.

`docs/product-focus-plan.md` section 7.3 asks every preset to spell out every
matcher flag, so a matcher added later cannot join a preset unnoticed. The
enumeration here is deliberately literal rather than generated from the preset
under test: a generated expectation would agree with any implementation.

`docs/contextual-term-tier-design.md` covers the dictionary tier. Terms whose
ordinary Korean usage takes an open complement set cannot be separated by any
rule, so they leave the default dictionary and return only when a caller asks
for them.

The name is `preset`, not `profile`: `benchmarks/` already uses
`engine_profile` for the matcher-isolating configurations it measures.
"""

import dataclasses

import pytest

from koguard import EngineConfig, KoguardDictionary, KoguardEngine
from koguard.config import MATCHER_FLAGS
from koguard.exceptions import DictionaryError

#: Every matcher stage, paired with the presets that enable it.
EXPECTED_PRESET_FLAGS: dict[str, dict[str, bool]] = {
    "exact_matching": {"strict": True, "balanced": True, "aggressive": True},
    "alias_matching": {"strict": True, "balanced": True, "aggressive": True},
    "repeated_matching": {"strict": False, "balanced": True, "aggressive": True},
    "separator_matching": {"strict": False, "balanced": True, "aggressive": True},
    "whitespace_gap_matching": {"strict": False, "balanced": True, "aggressive": True},
    "mixed_gap_matching": {"strict": False, "balanced": True, "aggressive": True},
    "choseong_matching": {"strict": False, "balanced": True, "aggressive": True},
    "keyboard_matching": {"strict": False, "balanced": True, "aggressive": True},
    "jamo_composition_matching": {"strict": False, "balanced": True, "aggressive": True},
    "segmented_input_matching": {"strict": False, "balanced": True, "aggressive": True},
    "fuzzy_matching": {"strict": False, "balanced": False, "aggressive": True},
}


def test_presets_classify_every_matcher_flag() -> None:
    """A new matcher stage must be placed in the table before it can ship.

    This is the guard plan section 7.3 asks for. Without it a stage added to
    `EngineConfig` would silently inherit whatever its field default says.
    """

    assert set(EXPECTED_PRESET_FLAGS) == set(MATCHER_FLAGS)


@pytest.mark.parametrize("preset_name", ["strict", "balanced", "aggressive"])
def test_each_preset_sets_every_matcher_flag_as_documented(preset_name: str) -> None:
    config: EngineConfig = getattr(EngineConfig, preset_name)()

    for flag, presets in EXPECTED_PRESET_FLAGS.items():
        assert getattr(config, flag) is presets[preset_name], flag


def test_zero_argument_config_is_the_balanced_preset() -> None:
    """`KoguardEngine()` must resolve to a named policy, not an unnamed one."""

    assert EngineConfig() == EngineConfig.balanced()


def test_presets_leave_the_cost_limits_at_their_defaults() -> None:
    """Presets choose detection stages. They are not a place to relax limits."""

    defaults = EngineConfig()
    for preset_name in ("strict", "balanced", "aggressive"):
        config: EngineConfig = getattr(EngineConfig, preset_name)()
        assert config.max_input_length == defaults.max_input_length
        assert config.max_whitespace_gap == defaults.max_whitespace_gap
        assert config.fuzzy_max_operations == defaults.fuzzy_max_operations
        assert config.fuzzy_max_index_entries == defaults.fuzzy_max_index_entries
        assert config.unicode_form == defaults.unicode_form


def test_a_preset_stays_narrowable() -> None:
    """A preset is a value, so callers keep the per-stage flags underneath it."""

    config = dataclasses.replace(EngineConfig.balanced(), choseong_matching=False)

    assert config.choseong_matching is False
    assert config.repeated_matching is True


def test_default_dictionary_excludes_the_contextual_tier() -> None:
    dictionary = KoguardDictionary.default()

    assert "꺼져" not in dictionary.blacklist
    assert "뒤질" not in dictionary.blacklist
    assert "닥쳐" in dictionary.blacklist, "layer-2 whitelist handles this one; it stays core"


def test_contextual_tier_loads_when_requested() -> None:
    dictionary = KoguardDictionary.default(include_contextual=True)

    assert "꺼져" in dictionary.blacklist
    assert "뒤질" in dictionary.blacklist


def test_contextual_tier_requires_the_packaged_defaults() -> None:
    """The tier is a slice of the packaged data, so it cannot stand alone."""

    with pytest.raises(DictionaryError, match="include_contextual"):
        KoguardDictionary.from_sources(include_defaults=False, include_contextual=True)


def test_default_engine_ignores_a_contextual_term_in_ordinary_korean() -> None:
    """The false positives that no rule could remove."""

    engine = KoguardEngine()

    assert engine.check("촛불이 바람에 꺼져 어두워졌다").detected is False
    assert engine.check("온 집을 뒤질 각오로 찾았다").detected is False


def test_default_engine_also_gives_up_the_contextual_term_as_an_insult() -> None:
    """The recall this costs, stated rather than hidden.

    `그만 꺼져` is a real insult and the default no longer flags it. The term is
    indistinguishable from its ordinary usage, so a service that needs it opts
    in and accepts the false positives that come with it.
    """

    assert KoguardEngine().check("그만 꺼져").detected is False


def test_opting_into_the_contextual_tier_detects_the_insult() -> None:
    engine = KoguardEngine(
        config=EngineConfig.aggressive(),
        dictionary=KoguardDictionary.default(include_contextual=True),
    )

    result = engine.check("그만 꺼져")

    assert result.detected is True
    assert [match.term for match in result.matches] == ["꺼져"]


def test_the_contextual_tier_still_honors_the_whitelist() -> None:
    """Opting in does not discard the layer-2 protections for the same term."""

    engine = KoguardEngine(
        config=EngineConfig.aggressive(),
        dictionary=KoguardDictionary.default(include_contextual=True),
    )

    assert engine.check("촛불이 바람에 꺼져 버렸다").detected is False
