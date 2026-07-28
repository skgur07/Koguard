"""Tests for immutable engine configuration."""

from typing import cast

import pytest

from koguard import ConfigurationError, EngineConfig, NormalizationForm


def test_engine_config_defaults() -> None:
    config = EngineConfig()

    assert config.max_input_length == 4096
    assert config.unicode_form == "NFKC"
    assert config.repeat_reduction_threshold == 2
    assert "*" in config.obfuscation_separators


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


@pytest.mark.parametrize("separators", [{"ab"}, {"a"}, {" "}, {""}])
def test_config_rejects_invalid_obfuscation_separators(separators: set[str]) -> None:
    with pytest.raises(ConfigurationError, match="obfuscation_separators"):
        EngineConfig(obfuscation_separators=frozenset(separators))
