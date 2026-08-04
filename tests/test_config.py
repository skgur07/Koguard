"""Tests for immutable engine configuration."""

from collections.abc import Callable
from typing import cast

import pytest

from koguard import ConfigurationError, EngineConfig, NormalizationForm


def test_engine_config_defaults() -> None:
    config = EngineConfig()

    assert config.max_input_length == 4096
    assert config.unicode_form == "NFKC"
    assert config.repeat_reduction_threshold == 2
    assert "*" in config.obfuscation_separators
    assert config.whitespace_gap_matching is True
    assert config.max_whitespace_gap == 3
    assert config.choseong_matching is True
    assert config.exact_matching is True
    assert config.repeated_matching is True
    assert config.separator_matching is True
    assert config.mixed_gap_matching is True


def test_engine_config_preserves_obfuscation_separator_positional_argument() -> None:
    config = EngineConfig(4096, "NFKC", 2, frozenset({"*"}))

    assert config.obfuscation_separators == frozenset({"*"})
    assert config.whitespace_gap_matching is True
    assert config.max_whitespace_gap == 3
    assert config.choseong_matching is True
    assert config.exact_matching is True
    assert config.repeated_matching is True
    assert config.separator_matching is True
    assert config.mixed_gap_matching is True


@pytest.mark.parametrize("value", [0, -1, False, 1.5])
def test_engine_config_rejects_invalid_max_length(value: object) -> None:
    with pytest.raises(ConfigurationError, match="positive integer"):
        EngineConfig(max_input_length=cast(int, value))


def test_engine_config_rejects_invalid_unicode_form() -> None:
    invalid_form = cast(NormalizationForm, "NFD")

    with pytest.raises(ConfigurationError, match="NFC"):
        EngineConfig(unicode_form=invalid_form)


@pytest.mark.parametrize("threshold", [True, 0, 1])
def test_engine_config_rejects_invalid_repeat_reduction_threshold(
    threshold: int,
) -> None:
    with pytest.raises(ConfigurationError, match="repeat_reduction_threshold"):
        EngineConfig(repeat_reduction_threshold=threshold)


@pytest.mark.parametrize(
    "field_name",
    [
        "exact_matching",
        "repeated_matching",
        "separator_matching",
        "whitespace_gap_matching",
        "mixed_gap_matching",
        "choseong_matching",
    ],
)
@pytest.mark.parametrize("enabled", [1, "yes", None])
def test_engine_config_rejects_invalid_matching_flag(
    field_name: str,
    enabled: object,
) -> None:
    config_factory = cast(Callable[..., EngineConfig], EngineConfig)

    with pytest.raises(ConfigurationError, match=field_name):
        config_factory(**{field_name: enabled})


@pytest.mark.parametrize("gap", [0, -1, True, 1.5])
def test_engine_config_rejects_invalid_max_whitespace_gap(gap: object) -> None:
    with pytest.raises(ConfigurationError, match="max_whitespace_gap"):
        EngineConfig(max_whitespace_gap=cast(int, gap))


@pytest.mark.parametrize("separators", [{"ab"}, {"a"}, {" "}, {""}])
def test_config_rejects_invalid_obfuscation_separators(separators: set[str]) -> None:
    with pytest.raises(ConfigurationError, match="obfuscation_separators"):
        EngineConfig(obfuscation_separators=frozenset(separators))


def test_config_rejects_mutable_obfuscation_separator_set() -> None:
    separators = cast(frozenset[str], {"*"})

    with pytest.raises(ConfigurationError, match="obfuscation_separators"):
        EngineConfig(obfuscation_separators=separators)


def test_config_normalizes_obfuscation_separators_with_unicode_form() -> None:
    config = EngineConfig(
        unicode_form="NFKC",
        obfuscation_separators=frozenset({"＊"}),
    )

    assert config.obfuscation_separators == frozenset({"*"})
