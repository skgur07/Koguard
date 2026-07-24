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
    occurrences: list[_NormalizedCandidate] = []
    search_from = 0
    while True:
        start = text.find(term, search_from)
        if start < 0:
            break
        occurrences.append(_NormalizedCandidate(term=term, start=start, end=start + len(term)))
        search_from = start + 1
    return tuple(occurrences)


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


class ExactMatcher:
    """Find literal normalized terms and remove protected spans."""

    __slots__ = ("_blacklist", "_whitelist")

    def __init__(self, dictionary: KoguardDictionary) -> None:
        self._blacklist = dictionary.ordered_blacklist
        self._whitelist = dictionary.ordered_whitelist

    def find(self, original_text: str, normalized: NormalizedText) -> tuple[Match, ...]:
        """Return deterministic, non-overlapping exact matches."""

        whitelist_spans = tuple(
            _map_candidate(candidate, normalized)
            for term in self._whitelist
            for candidate in _find_occurrences(normalized.text, term)
        )
        candidates = [
            _map_candidate(candidate, normalized)
            for term in self._blacklist
            for candidate in _find_occurrences(normalized.text, term)
        ]
        candidates = [
            candidate
            for candidate in candidates
            if not any(candidate.overlaps(protected) for protected in whitelist_spans)
        ]

        selected: list[_MappedCandidate] = []
        for candidate in sorted(
            candidates,
            key=lambda item: (
                -item.length,
                item.original_start,
                item.normalized.term,
            ),
        ):
            if not any(candidate.overlaps(existing) for existing in selected):
                selected.append(candidate)

        matches: list[Match] = []
        for candidate in sorted(
            selected,
            key=lambda item: (
                item.original_start,
                item.original_end,
                item.normalized.term,
            ),
        ):
            matches.append(
                Match(
                    term=candidate.normalized.term,
                    matched_text=original_text[candidate.original_start : candidate.original_end],
                    start=candidate.original_start,
                    end=candidate.original_end,
                    method=MatchMethod.EXACT,
                    score=1.0,
                )
            )
        return tuple(matches)
