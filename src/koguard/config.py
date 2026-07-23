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

    def __post_init__(self) -> None:
        if isinstance(self.max_input_length, bool) or self.max_input_length <= 0:
            raise ConfigurationError("max_input_length must be a positive integer")
        if self.unicode_form not in {"NFC", "NFKC"}:
            raise ConfigurationError("unicode_form must be either 'NFC' or 'NFKC'")
