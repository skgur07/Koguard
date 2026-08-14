"""Public synchronous engine entry point."""

from time import perf_counter_ns

from koguard.config import EngineConfig, ProfileName, _config_for_profile
from koguard.engine.dictionary import KoguardDictionary
from koguard.engine.matcher import (
    AliasMatcher,
    ChoseongMatcher,
    ExactMatcher,
    FuzzyMatcher,
    _ProtectedMasks,
)
from koguard.engine.normalizer import (
    build_dubeolsik_view,
    build_jamo_composition_view,
    build_repeated_view,
    build_segmented_choseong_view,
    build_segmented_dubeolsik_view,
    build_segmented_jamo_composition_view,
    build_separator_view,
    has_compatibility_choseong_input,
    normalize_text,
)
from koguard.exceptions import ConfigurationError, InputTooLongError
from koguard.models import CheckResult, Match, MatchMethod


def _union_original_masks(
    original_length: int,
    *protected_masks: _ProtectedMasks,
) -> bytes:
    """Union view-local Whitelist spans into one original-text mask."""

    combined = bytearray(original_length)
    for protected in protected_masks:
        for index, value in enumerate(protected.original):
            if value:
                combined[index] = 1
    return bytes(combined)


def _merge_view_matches(
    original_length: int,
    *match_groups: tuple[Match, ...],
    protected_original_masks: tuple[bytes, ...] = (),
) -> tuple[Match, ...]:
    occupied = bytearray(original_length)
    selected: list[Match] = []
    for matches in match_groups:
        for match in matches:
            if any(
                protected_mask.find(b"\x01", match.start, match.end) >= 0
                for protected_mask in protected_original_masks
            ):
                continue
            if occupied.find(b"\x01", match.start, match.end) >= 0:
                continue
            selected.append(match)
            occupied[match.start : match.end] = b"\x01" * (match.end - match.start)
    return tuple(
        sorted(
            selected,
            key=lambda match: (match.start, match.end, match.term),
        )
    )


def _build_match_original_mask(
    original_length: int,
    matches: tuple[Match, ...],
) -> bytes:
    """Return original positions already occupied by higher-priority matches."""

    occupied = bytearray(original_length)
    for match in matches:
        occupied[match.start : match.end] = b"\x01" * (match.end - match.start)
    return bytes(occupied)


class KoguardEngine:
    """Synchronous, thread-safe profanity detection engine."""

    __slots__ = (
        "_alias_matcher",
        "_choseong_matcher",
        "_config",
        "_dictionary",
        "_exact_matcher",
        "_fuzzy_matcher",
    )

    def __init__(
        self,
        *,
        profile: ProfileName | None = None,
        config: EngineConfig | None = None,
        dictionary: KoguardDictionary | None = None,
    ) -> None:
        if profile is not None and config is not None:
            raise ConfigurationError("profile and config cannot be provided together")
        profile_name: object = "balanced" if profile is None else profile
        resolved_config = config if config is not None else _config_for_profile(profile_name)
        resolved_dictionary = dictionary or KoguardDictionary.default(resolved_config.unicode_form)

        if resolved_dictionary.unicode_form != resolved_config.unicode_form:
            raise ConfigurationError("dictionary unicode_form must match the engine configuration")

        self._config = resolved_config
        self._dictionary = resolved_dictionary
        self._exact_matcher = ExactMatcher(
            resolved_dictionary,
            whitespace_gap_matching=resolved_config.whitespace_gap_matching,
            mixed_gap_matching=resolved_config.mixed_gap_matching,
        )
        self._choseong_matcher = (
            ChoseongMatcher(resolved_dictionary) if resolved_config.choseong_matching else None
        )
        self._alias_matcher = (
            AliasMatcher(resolved_dictionary) if resolved_config.alias_matching else None
        )
        self._fuzzy_matcher = (
            FuzzyMatcher(
                resolved_dictionary,
                min_term_length=resolved_config.fuzzy_min_term_length,
                max_term_length=resolved_config.fuzzy_max_term_length,
                max_distance=resolved_config.fuzzy_max_distance,
                min_score=resolved_config.fuzzy_min_score,
                max_operations=resolved_config.fuzzy_max_operations,
                max_index_entries=resolved_config.fuzzy_max_index_entries,
            )
            if resolved_config.fuzzy_matching
            else None
        )

    @property
    def config(self) -> EngineConfig:
        """The immutable engine configuration."""

        return self._config

    @property
    def dictionary(self) -> KoguardDictionary:
        """The immutable dictionary used by this engine."""

        return self._dictionary

    def contains(self, text: str) -> bool:
        """Return whether ``check(text)`` detects at least one match."""

        return self.check(text).detected

    def check(self, text: str) -> CheckResult:
        """Check one input string and return every non-whitelisted profanity match."""

        if not isinstance(text, str):
            raise TypeError("text must be a string")
        if len(text) > self._config.max_input_length:
            raise InputTooLongError(len(text), self._config.max_input_length)

        started_at = perf_counter_ns()
        normalized = normalize_text(text, self._config.unicode_form)
        keyboard = (
            build_dubeolsik_view(normalized) if self._config.keyboard_matching else normalized
        )
        jamo_composed = (
            build_jamo_composition_view(
                text,
                self._config.unicode_form,
                normalized=normalized,
            )
            if self._config.jamo_composition_matching
            else normalized
        )
        segmented_keyboard = keyboard
        segmented_jamo = jamo_composed
        segmented_choseong = normalized
        has_segmented_source = (
            keyboard is not normalized
            or jamo_composed is not normalized
            or (self._config.choseong_matching and has_compatibility_choseong_input(text))
        )
        if self._config.segmented_input_matching and has_segmented_source:
            has_segmented_gap = " " in normalized.text or not (
                self._config.obfuscation_separators.isdisjoint(normalized.text)
            )
        else:
            has_segmented_gap = False
        if has_segmented_gap:
            if self._config.keyboard_matching and keyboard is not normalized:
                segmented_keyboard = build_segmented_dubeolsik_view(
                    text,
                    normalized,
                    separators=self._config.obfuscation_separators,
                    max_whitespace_gap=self._config.max_whitespace_gap,
                )
            if self._config.jamo_composition_matching and jamo_composed is not normalized:
                segmented_jamo = build_segmented_jamo_composition_view(
                    text,
                    self._config.unicode_form,
                    normalized=normalized,
                    separators=self._config.obfuscation_separators,
                    max_whitespace_gap=self._config.max_whitespace_gap,
                )
            if self._config.choseong_matching:
                segmented_choseong = build_segmented_choseong_view(
                    text,
                    normalized,
                    separators=self._config.obfuscation_separators,
                    max_whitespace_gap=self._config.max_whitespace_gap,
                )
        repeated = (
            build_repeated_view(
                normalized,
                threshold=self._config.repeat_reduction_threshold,
            )
            if self._config.repeated_matching
            else normalized
        )
        separated = (
            build_separator_view(
                normalized,
                separators=self._config.obfuscation_separators,
            )
            if self._config.separator_matching
            else normalized
        )

        normalized_protected = self._exact_matcher.build_protected_masks(text, normalized)
        repeated_protected = (
            normalized_protected
            if repeated == normalized
            else self._exact_matcher.build_protected_masks(text, repeated)
        )
        if separated == normalized:
            separated_protected = normalized_protected
        elif separated == repeated:
            separated_protected = repeated_protected
        else:
            separated_protected = self._exact_matcher.build_protected_masks(text, separated)
        keyboard_protected = (
            normalized_protected
            if keyboard == normalized
            else self._exact_matcher.build_protected_masks(text, keyboard)
        )
        jamo_composed_protected = (
            normalized_protected
            if jamo_composed == normalized
            else self._exact_matcher.build_protected_masks(text, jamo_composed)
        )
        segmented_keyboard_protected = (
            keyboard_protected
            if segmented_keyboard == keyboard
            else self._exact_matcher.build_protected_masks(text, segmented_keyboard)
        )
        segmented_jamo_protected = (
            jamo_composed_protected
            if segmented_jamo == jamo_composed
            else self._exact_matcher.build_protected_masks(text, segmented_jamo)
        )
        segmented_choseong_protected = (
            normalized_protected
            if segmented_choseong == normalized
            else self._exact_matcher.build_protected_masks(text, segmented_choseong)
        )
        segmented_protected_masks = tuple(
            protected
            for view_changed, protected in (
                (segmented_keyboard != keyboard, segmented_keyboard_protected),
                (segmented_jamo != jamo_composed, segmented_jamo_protected),
                (segmented_choseong != normalized, segmented_choseong_protected),
            )
            if view_changed
        )
        protected_original = _union_original_masks(
            len(text),
            normalized_protected,
            repeated_protected,
            separated_protected,
            keyboard_protected,
            jamo_composed_protected,
            *segmented_protected_masks,
        )

        exact_matches: tuple[Match, ...] = ()
        if self._config.exact_matching:
            exact_matches = self._exact_matcher.find(
                text,
                normalized,
                protected_masks=normalized_protected,
                protected_original=protected_original,
            )
        repeated_matches: tuple[Match, ...] = ()
        if self._config.repeated_matching and repeated != normalized:
            repeated_matches = self._exact_matcher.find(
                text,
                repeated,
                method=MatchMethod.REPEATED,
                protected_masks=repeated_protected,
                protected_original=protected_original,
            )
        separator_matches: tuple[Match, ...] = ()
        if self._config.separator_matching and separated != normalized:
            separator_matches = self._exact_matcher.find(
                text,
                separated,
                method=MatchMethod.SEPARATOR,
                protected_masks=separated_protected,
                protected_original=protected_original,
            )
        whitespace_matches: tuple[Match, ...] = ()
        if self._config.whitespace_gap_matching:
            whitespace_matches = self._exact_matcher.find_with_whitespace_gaps(
                text,
                normalized,
                max_whitespace_gap=self._config.max_whitespace_gap,
                protected_masks=normalized_protected,
                protected_original=protected_original,
            )
        keyboard_matches: tuple[Match, ...] = ()
        if self._config.keyboard_matching and keyboard != normalized:
            keyboard_matches = self._exact_matcher.find(
                text,
                keyboard,
                method=MatchMethod.KEYBOARD,
                protected_masks=keyboard_protected,
                protected_original=protected_original,
            )
        jamo_matches: tuple[Match, ...] = ()
        if self._config.jamo_composition_matching and jamo_composed != normalized:
            jamo_matches = self._exact_matcher.find(
                text,
                jamo_composed,
                method=MatchMethod.JAMO,
                protected_masks=jamo_composed_protected,
                protected_original=protected_original,
            )
        segmented_keyboard_matches: tuple[Match, ...] = ()
        if self._config.segmented_input_matching and segmented_keyboard != keyboard:
            segmented_keyboard_matches = self._exact_matcher.find(
                text,
                segmented_keyboard,
                method=MatchMethod.KEYBOARD,
                protected_masks=segmented_keyboard_protected,
                protected_original=protected_original,
            )
        segmented_jamo_matches: tuple[Match, ...] = ()
        if self._config.segmented_input_matching and segmented_jamo != jamo_composed:
            segmented_jamo_matches = self._exact_matcher.find(
                text,
                segmented_jamo,
                method=MatchMethod.JAMO,
                protected_masks=segmented_jamo_protected,
                protected_original=protected_original,
            )
        choseong_matches: tuple[Match, ...] = ()
        alias_matches: tuple[Match, ...] = ()
        if self._alias_matcher is not None:
            alias_matches = self._alias_matcher.find(
                text,
                normalized,
                protected_masks=normalized_protected,
                protected_original=protected_original,
            )
        if self._choseong_matcher is not None:
            choseong_matches = self._choseong_matcher.find(
                text,
                normalized,
                protected_masks=normalized_protected,
                protected_original=protected_original,
            )
        segmented_choseong_matches: tuple[Match, ...] = ()
        if (
            self._config.segmented_input_matching
            and self._choseong_matcher is not None
            and segmented_choseong != normalized
        ):
            segmented_choseong_matches = self._choseong_matcher.find(
                text,
                segmented_choseong,
                protected_masks=segmented_choseong_protected,
                protected_original=protected_original,
            )

        matches = _merge_view_matches(
            len(text),
            exact_matches,
            repeated_matches,
            separator_matches,
            whitespace_matches,
            keyboard_matches,
            jamo_matches,
            segmented_keyboard_matches,
            segmented_jamo_matches,
            alias_matches,
            choseong_matches,
            segmented_choseong_matches,
            protected_original_masks=(protected_original,),
        )
        if self._config.mixed_gap_matching:
            mixed_matches = self._exact_matcher.find_with_mixed_gaps(
                text,
                normalized,
                max_whitespace_gap=self._config.max_whitespace_gap,
                separators=self._config.obfuscation_separators,
                protected_original=protected_original,
                occupied_original=_build_match_original_mask(len(text), matches),
            )
            matches = _merge_view_matches(
                len(text),
                matches,
                mixed_matches,
                protected_original_masks=(protected_original,),
            )
        if self._fuzzy_matcher is not None:
            fuzzy_matches = self._fuzzy_matcher.find(
                text,
                normalized,
                protected_masks=normalized_protected,
                protected_original=protected_original,
                occupied_original=_build_match_original_mask(len(text), matches),
            )
            matches = _merge_view_matches(
                len(text),
                matches,
                fuzzy_matches,
                protected_original_masks=(protected_original,),
            )
        elapsed_ms = (perf_counter_ns() - started_at) / 1_000_000

        return CheckResult(
            normalized_text=normalized.text,
            matches=matches,
            elapsed_ms=elapsed_ms,
        )
