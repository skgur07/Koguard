"""Tests for immutable engine configuration."""

from typing import cast

import pytest

from koguard import ConfigurationError, EngineConfig, NormalizationForm


def test_engine_config_defaults() -> None:
    config = EngineConfig()

    assert config.max_input_length == 4096
    assert config.unicode_form == "NFKC"


@pytest.mark.parametrize("value", [0, -1, False])
def test_engine_config_rejects_invalid_max_length(value: int) -> None:
    with pytest.raises(ConfigurationError, match="positive integer"):
        EngineConfig(max_input_length=value)


def test_engine_config_rejects_invalid_unicode_form() -> None:
    invalid_form = cast(NormalizationForm, "NFD")

    with pytest.raises(ConfigurationError, match="NFC"):
        EngineConfig(unicode_form=invalid_form)
