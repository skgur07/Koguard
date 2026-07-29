"""Configuration models for the Koguard engine."""

from dataclasses import dataclass
from typing import Literal, TypeAlias
from unicodedata import normalize

from koguard.exceptions import ConfigurationError

NormalizationForm: TypeAlias = Literal["NFC", "NFKC"]


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Immutable configuration shared by Koguard engine components."""

    max_input_length: int = 4096
    unicode_form: NormalizationForm = "NFKC"
    repeat_reduction_threshold: int = 2
    whitespace_gap_matching: bool = False
    max_whitespace_gap: int = 3
    obfuscation_separators: frozenset[str] = frozenset("!@#$%^&*_-+=~.·,")

    def __post_init__(self) -> None:
        if type(self.max_input_length) is not int or self.max_input_length <= 0:
            raise ConfigurationError("max_input_length must be a positive integer")
        if self.unicode_form not in {"NFC", "NFKC"}:
            raise ConfigurationError("unicode_form must be either 'NFC' or 'NFKC'")
        if type(self.repeat_reduction_threshold) is not int or self.repeat_reduction_threshold < 2:
            raise ConfigurationError(
                "repeat_reduction_threshold must be an integer greater than or equal to 2"
            )
        if type(self.whitespace_gap_matching) is not bool:
            raise ConfigurationError("whitespace_gap_matching must be a boolean")
        if type(self.max_whitespace_gap) is not int or self.max_whitespace_gap <= 0:
            raise ConfigurationError("max_whitespace_gap must be a positive integer")
        if not isinstance(self.obfuscation_separators, frozenset):
            raise ConfigurationError(
                "obfuscation_separators must be a frozenset of single "
                "non-alphanumeric, non-whitespace characters"
            )
        normalized_separators = frozenset(
            normalize(self.unicode_form, separator) for separator in self.obfuscation_separators
        )
        if any(
            len(separator) != 1 or separator.isalnum() or separator.isspace()
            for separator in normalized_separators
        ):
            raise ConfigurationError(
                "obfuscation_separators must normalize to single "
                "non-alphanumeric, non-whitespace characters"
            )
        object.__setattr__(self, "obfuscation_separators", normalized_separators)
