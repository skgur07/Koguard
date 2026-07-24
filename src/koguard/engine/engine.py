"""Public synchronous engine entry point."""

from time import perf_counter_ns

from koguard.config import EngineConfig
from koguard.engine.dictionary import KoguardDictionary
from koguard.engine.matcher import ExactMatcher
from koguard.engine.normalizer import normalize_text
from koguard.exceptions import ConfigurationError, InputTooLongError
from koguard.models import CheckResult


class KoguardEngine:
    """Synchronous, thread-safe profanity detection engine."""

    __slots__ = ("_config", "_dictionary", "_exact_matcher")

    def __init__(
        self,
        *,
        config: EngineConfig | None = None,
        dictionary: KoguardDictionary | None = None,
    ) -> None:
        resolved_config = config or EngineConfig()
        resolved_dictionary = dictionary or KoguardDictionary.default(resolved_config.unicode_form)

        if resolved_dictionary.unicode_form != resolved_config.unicode_form:
            raise ConfigurationError("dictionary unicode_form must match the engine configuration")

        self._config = resolved_config
        self._dictionary = resolved_dictionary
        self._exact_matcher = ExactMatcher(resolved_dictionary)

    @property
    def config(self) -> EngineConfig:
        """The immutable engine configuration."""

        return self._config

    @property
    def dictionary(self) -> KoguardDictionary:
        """The immutable dictionary used by this engine."""

        return self._dictionary

    def check(self, text: str) -> CheckResult:
        """Check one input string and return every non-whitelisted exact match."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if len(text) > self._config.max_input_length:
            raise InputTooLongError(len(text), self._config.max_input_length)

        started_at = perf_counter_ns()
        normalized = normalize_text(text, self._config.unicode_form)
        matches = self._exact_matcher.find(text, normalized)
        elapsed_ms = (perf_counter_ns() - started_at) / 1_000_000

        return CheckResult(
            normalized_text=normalized.text,
            matches=matches,
            elapsed_ms=elapsed_ms,
        )
