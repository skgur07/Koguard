"""Public synchronous engine entry point."""

from time import perf_counter_ns

from koguard.config import EngineConfig
from koguard.engine.dictionary import KoguardDictionary
from koguard.engine.matcher import ExactMatcher
from koguard.engine.normalizer import build_repeated_view, normalize_text
from koguard.exceptions import ConfigurationError, InputTooLongError
from koguard.models import CheckResult, Match, MatchMethod


def _merge_view_matches(
    original_length: int,
    exact_matches: tuple[Match, ...],
    repeated_matches: tuple[Match, ...],
) -> tuple[Match, ...]:
    occupied = bytearray(original_length)
    selected: list[Match] = []
    for match in (*exact_matches, *repeated_matches):
        if match.start is None or match.end is None:
            continue
        if occupied.find(b"\x01", match.start, match.end) >= 0:
            continue
        selected.append(match)
        occupied[match.start : match.end] = b"\x01" * (match.end - match.start)
    return tuple(
        sorted(
            selected,
            key=lambda match: (
                match.start if match.start is not None else -1,
                match.end if match.end is not None else -1,
                match.term,
            ),
        )
    )


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
        exact_matches = self._exact_matcher.find(text, normalized)
        repeated = build_repeated_view(
            normalized,
            threshold=self._config.repeat_reduction_threshold,
        )
        repeated_matches: tuple[Match, ...] = ()
        if repeated != normalized:
            repeated_matches = self._exact_matcher.find(
                text,
                repeated,
                method=MatchMethod.REPEATED,
            )
        matches = _merge_view_matches(len(text), exact_matches, repeated_matches)
        elapsed_ms = (perf_counter_ns() - started_at) / 1_000_000

        return CheckResult(
            normalized_text=normalized.text,
            matches=matches,
            elapsed_ms=elapsed_ms,
        )
