"""Low-cost exact matching with span-scoped whitelist protection."""

from dataclasses import dataclass

from koguard.engine.dictionary import KoguardDictionary
from koguard.engine.normalizer import NormalizedText
from koguard.models import Match, MatchMethod


@dataclass(frozen=True, slots=True)
class _NormalizedCandidate:
    term: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return self.end - self.start

    def overlaps(self, other: "_NormalizedCandidate") -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True, slots=True)
class _MappedCandidate:
    normalized: _NormalizedCandidate
    original_start: int
    original_end: int

    @property
    def length(self) -> int:
        return self.normalized.length

    def overlaps(self, other: "_MappedCandidate") -> bool:
        normalized_overlap = self.normalized.overlaps(other.normalized)
        original_overlap = (
            self.original_start < other.original_end and other.original_start < self.original_end
        )
        return normalized_overlap or original_overlap


def _find_occurrences(text: str, term: str) -> tuple[_NormalizedCandidate, ...]:
    """Find overlapping occurrences through CPython's optimized string search."""

    occurrences: list[_NormalizedCandidate] = []
    search_from = 0
    while True:
        start = text.find(term, search_from)
        if start < 0:
            return tuple(occurrences)
        occurrences.append(
            _NormalizedCandidate(
                term=term,
                start=start,
                end=start + len(term),
            )
        )
        search_from = start + 1


def _map_candidate(
    candidate: _NormalizedCandidate,
    normalized: NormalizedText,
) -> _MappedCandidate:
    original_start, original_end = normalized.original_span(
        candidate.start,
        candidate.end,
    )
    return _MappedCandidate(
        normalized=candidate,
        original_start=original_start,
        original_end=original_end,
    )


def _overlaps_mask(mask: bytearray, start: int, end: int) -> bool:
    return mask.find(b"\x01", start, end) >= 0


def _mark_mask(mask: bytearray, start: int, end: int) -> None:
    mask[start:end] = b"\x01" * (end - start)


def _is_occupied(
    candidate: _MappedCandidate,
    normalized_mask: bytearray,
    original_mask: bytearray,
) -> bool:
    return _overlaps_mask(
        normalized_mask,
        candidate.normalized.start,
        candidate.normalized.end,
    ) or _overlaps_mask(
        original_mask,
        candidate.original_start,
        candidate.original_end,
    )


def _occupy(
    candidate: _MappedCandidate,
    normalized_mask: bytearray,
    original_mask: bytearray,
) -> None:
    _mark_mask(
        normalized_mask,
        candidate.normalized.start,
        candidate.normalized.end,
    )
    _mark_mask(
        original_mask,
        candidate.original_start,
        candidate.original_end,
    )


class ExactMatcher:
    """Find normalized terms and remove protected or overlapping spans."""

    __slots__ = ("_blacklist", "_whitelist")

    def __init__(self, dictionary: KoguardDictionary) -> None:
        self._blacklist = dictionary.ordered_blacklist
        self._whitelist = dictionary.ordered_whitelist

    def find(self, original_text: str, normalized: NormalizedText) -> tuple[Match, ...]:
        """Return deterministic, non-overlapping exact matches."""

        protected_normalized = bytearray(len(normalized.text))
        protected_original = bytearray(len(original_text))
        for term in self._whitelist:
            for normalized_candidate in _find_occurrences(normalized.text, term):
                _occupy(
                    _map_candidate(normalized_candidate, normalized),
                    protected_normalized,
                    protected_original,
                )

        candidates = [
            _map_candidate(normalized_candidate, normalized)
            for term in self._blacklist
            for normalized_candidate in _find_occurrences(normalized.text, term)
        ]

        selected_normalized = bytearray(len(normalized.text))
        selected_original = bytearray(len(original_text))
        selected: list[_MappedCandidate] = []
        for mapped_candidate in sorted(
            candidates,
            key=lambda item: (
                -item.length,
                item.original_start,
                item.normalized.term,
            ),
        ):
            if _is_occupied(
                mapped_candidate,
                protected_normalized,
                protected_original,
            ):
                continue
            if _is_occupied(
                mapped_candidate,
                selected_normalized,
                selected_original,
            ):
                continue
            selected.append(mapped_candidate)
            _occupy(mapped_candidate, selected_normalized, selected_original)

        matches: list[Match] = []
        for mapped_candidate in sorted(
            selected,
            key=lambda item: (
                item.original_start,
                item.original_end,
                item.normalized.term,
            ),
        ):
            matches.append(
                Match(
                    term=mapped_candidate.normalized.term,
                    matched_text=original_text[
                        mapped_candidate.original_start : mapped_candidate.original_end
                    ],
                    start=mapped_candidate.original_start,
                    end=mapped_candidate.original_end,
                    method=MatchMethod.EXACT,
                    score=1.0,
                )
            )
        return tuple(matches)
