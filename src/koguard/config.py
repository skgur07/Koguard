"""Configuration models for the Koguard engine."""

from dataclasses import dataclass
from typing import Literal, TypeAlias
from unicodedata import normalize

from koguard.exceptions import ConfigurationError

NormalizationForm: TypeAlias = Literal["NFC", "NFKC"]

#: Every detection stage that can be switched on or off, in the order the
#: README documents them. Presets and validation both read this list, so a new
#: stage cannot be added to one and forgotten in the other.
MATCHER_FLAGS: tuple[str, ...] = (
    "exact_matching",
    "repeated_matching",
    "separator_matching",
    "whitespace_gap_matching",
    "mixed_gap_matching",
    "choseong_matching",
    "alias_matching",
    "keyboard_matching",
    "jamo_composition_matching",
    "segmented_input_matching",
    "fuzzy_matching",
)


@dataclass(frozen=True, slots=True)
class EngineConfig:
    """Immutable configuration shared by Koguard engine components."""

    max_input_length: int = 4096
    unicode_form: NormalizationForm = "NFKC"
    repeat_reduction_threshold: int = 2
    obfuscation_separators: frozenset[str] = frozenset("!@#$%^&*_-+=~.·,")
    whitespace_gap_matching: bool = True
    max_whitespace_gap: int = 3
    choseong_matching: bool = True
    exact_matching: bool = True
    repeated_matching: bool = True
    separator_matching: bool = True
    mixed_gap_matching: bool = True
    alias_matching: bool = True
    keyboard_matching: bool = True
    jamo_composition_matching: bool = True
    segmented_input_matching: bool = True
    fuzzy_matching: bool = False
    fuzzy_min_term_length: int = 3
    fuzzy_max_term_length: int = 32
    fuzzy_max_distance: int = 1
    fuzzy_min_score: float = 0.0
    fuzzy_max_operations: int = 250_000
    fuzzy_max_index_entries: int = 100_000

    def __post_init__(self) -> None:
        if type(self.max_input_length) is not int or self.max_input_length <= 0:
            raise ConfigurationError("max_input_length must be a positive integer")
        if self.unicode_form not in {"NFC", "NFKC"}:
            raise ConfigurationError("unicode_form must be either 'NFC' or 'NFKC'")
        if type(self.repeat_reduction_threshold) is not int or self.repeat_reduction_threshold < 2:
            raise ConfigurationError(
                "repeat_reduction_threshold must be an integer greater than or equal to 2"
            )
        for field_name in MATCHER_FLAGS:
            if type(getattr(self, field_name)) is not bool:
                raise ConfigurationError(f"{field_name} must be a boolean")
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
        if type(self.fuzzy_min_term_length) is not int or self.fuzzy_min_term_length < 3:
            raise ConfigurationError("fuzzy_min_term_length must be an integer of at least 3")
        if (
            type(self.fuzzy_max_term_length) is not int
            or self.fuzzy_max_term_length < self.fuzzy_min_term_length
        ):
            raise ConfigurationError(
                "fuzzy_max_term_length must be an integer greater than or equal to "
                "fuzzy_min_term_length"
            )
        if (
            type(self.fuzzy_max_distance) is not int
            or not 1 <= self.fuzzy_max_distance <= 2
            or self.fuzzy_max_distance >= self.fuzzy_min_term_length
        ):
            raise ConfigurationError(
                "fuzzy_max_distance must be 1 or 2 and less than fuzzy_min_term_length"
            )
        if (
            isinstance(self.fuzzy_min_score, bool)
            or not isinstance(self.fuzzy_min_score, (int, float))
            or not 0.0 <= self.fuzzy_min_score <= 1.0
        ):
            raise ConfigurationError("fuzzy_min_score must be a number between 0.0 and 1.0")
        object.__setattr__(self, "fuzzy_min_score", float(self.fuzzy_min_score))
        if type(self.fuzzy_max_operations) is not int or self.fuzzy_max_operations <= 0:
            raise ConfigurationError("fuzzy_max_operations must be a positive integer")
        if type(self.fuzzy_max_index_entries) is not int or self.fuzzy_max_index_entries <= 0:
            raise ConfigurationError("fuzzy_max_index_entries must be a positive integer")

    # Presets are values, not a separate policy layer: they return an ordinary
    # ``EngineConfig`` that callers can narrow with ``dataclasses.replace``.
    # Every stage is spelled out in every preset so that adding a stage forces a
    # decision here rather than inheriting a field default. The measured cost of
    # each choice is in ``docs/accuracy-baseline.md``.

    @classmethod
    def strict(cls) -> "EngineConfig":
        """Dictionary terms and explicit aliases only.

        The lowest-latency policy, not the most precise one: on the evaluation
        corpus the obfuscation stages add no false positives, so what this gives
        up is recall rather than precision.
        """

        return cls(
            exact_matching=True,
            repeated_matching=False,
            separator_matching=False,
            whitespace_gap_matching=False,
            mixed_gap_matching=False,
            choseong_matching=False,
            alias_matching=True,
            keyboard_matching=False,
            jamo_composition_matching=False,
            segmented_input_matching=False,
            fuzzy_matching=False,
        )

    @classmethod
    def balanced(cls) -> "EngineConfig":
        """Every obfuscation stage, without fuzzy matching.

        What ``EngineConfig()`` resolves to. Fuzzy is excluded because it found
        nothing the other stages missed and only produced false positives.
        """

        return cls(
            exact_matching=True,
            repeated_matching=True,
            separator_matching=True,
            whitespace_gap_matching=True,
            mixed_gap_matching=True,
            choseong_matching=True,
            alias_matching=True,
            keyboard_matching=True,
            jamo_composition_matching=True,
            segmented_input_matching=True,
            fuzzy_matching=False,
        )

    @classmethod
    def aggressive(cls) -> "EngineConfig":
        """Every stage, fuzzy matching included.

        Pair it with ``KoguardDictionary.default(include_contextual=True)`` to
        also cover terms whose ordinary Korean usage is indistinguishable. Both
        halves raise false positives; neither bypasses the whitelist or the
        configured cost limits.
        """

        return cls(
            exact_matching=True,
            repeated_matching=True,
            separator_matching=True,
            whitespace_gap_matching=True,
            mixed_gap_matching=True,
            choseong_matching=True,
            alias_matching=True,
            keyboard_matching=True,
            jamo_composition_matching=True,
            segmented_input_matching=True,
            fuzzy_matching=True,
        )
