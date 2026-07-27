"""Configuration models for the Koguard engine."""

from dataclasses import dataclass
from typing import Literal, TypeAlias

from koguard.exceptions import ConfigurationError

NormalizationForm: TypeAlias = Literal["NFC", "NFKC"]


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Immutable configuration shared by Koguard engine components."""

    max_input_length: int = 4096
    unicode_form: NormalizationForm = "NFKC"
    repeat_reduction_threshold: int = 2

    def __post_init__(self) -> None:
        if type(self.max_input_length) is not int or self.max_input_length <= 0:
            raise ConfigurationError("max_input_length must be a positive integer")
        if self.unicode_form not in {"NFC", "NFKC"}:
            raise ConfigurationError("unicode_form must be either 'NFC' or 'NFKC'")
        if type(self.repeat_reduction_threshold) is not int or self.repeat_reduction_threshold < 2:
            raise ConfigurationError(
                "repeat_reduction_threshold must be an integer greater than or equal to 2"
            )
