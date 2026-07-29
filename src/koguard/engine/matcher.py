"""Low-cost exact matching with span-scoped whitelist protection."""

from collections.abc import Iterator
from dataclasses import dataclass, field

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
        return len(self.term)


@dataclass(frozen=True, slots=True)
class _MappedCandidate:
    normalized: _NormalizedCandidate
    original_start: int
    original_end: int

    @property
    def length(self) -> int:
        return self.normalized.length


@dataclass(slots=True)
class _WhitespaceTrieNode:
    children: dict[str, "_WhitespaceTrieNode"] = field(default_factory=dict)
    term: str | None = None


def _iter_occurrences(text: str, term: str) -> Iterator[_NormalizedCandidate]:
    """Find overlapping occurrences through CPython's optimized string search."""

    search_from = 0
    while True:
        start = text.find(term, search_from)
        if start < 0:
            return
        yield _NormalizedCandidate(
            term=term,
            start=start,
            end=start + len(term),
        )
        search_from = start + 1


def _is_allowed_whitespace_gap(
    original_text: str,
    normalized: NormalizedText,
    index: int,
    max_whitespace_gap: int,
) -> bool:
    original_start, original_end = normalized.source_spans[index]
    gap = original_text[original_start:original_end]
    return len(gap) <= max_whitespace_gap and all(character in {" ", "\t"} for character in gap)


def _has_alphanumeric_boundaries(text: str, start: int, end: int) -> bool:
    return (start == 0 or not text[start - 1].isalnum()) and (
        end == len(text) or not text[end].isalnum()
    )


def _build_whitespace_trie(terms: tuple[str, ...]) -> _WhitespaceTrieNode:
    root = _WhitespaceTrieNode()
    for term in terms:
        if len(term) < 2 or any(character.isspace() for character in term):
            continue
        node = root
        for character in term:
            node = node.children.setdefault(character, _WhitespaceTrieNode())
        node.term = term
    return root


def _iter_whitespace_gap_occurrences(
    original_text: str,
    normalized: NormalizedText,
    root: _WhitespaceTrieNode,
    max_whitespace_gap: int,
) -> Iterator[_NormalizedCandidate]:
    """Find terms whose characters are separated by bounded spaces or tabs."""

    for start, first_character in enumerate(normalized.text):
        node = root.children.get(first_character)
        if node is None:
            continue
        cursor = start + 1
        used_gap = False
        while cursor < len(normalized.text):
            if normalized.text[cursor] == " ":
                if not _is_allowed_whitespace_gap(
                    original_text,
                    normalized,
                    cursor,
                    max_whitespace_gap,
                ):
                    break
                used_gap = True
                cursor += 1
            if cursor >= len(normalized.text):
                break

            node = node.children.get(normalized.text[cursor])
            if node is None:
                break
            cursor += 1
            if (
                node.term is not None
                and used_gap
                and _has_alphanumeric_boundaries(normalized.text, start, cursor)
            ):
                yield _NormalizedCandidate(term=node.term, start=start, end=cursor)


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

    __slots__ = ("_blacklist", "_whitelist", "_whitespace_trie")

    def __init__(
        self,
        dictionary: KoguardDictionary,
        *,
        whitespace_gap_matching: bool = True,
    ) -> None:
        self._blacklist = dictionary.ordered_blacklist
        self._whitelist = dictionary.ordered_whitelist
        self._whitespace_trie = (
            _build_whitespace_trie(self._blacklist) if whitespace_gap_matching else None
        )

    def find(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        method: MatchMethod = MatchMethod.EXACT,
    ) -> tuple[Match, ...]:
        """Return deterministic, non-overlapping exact matches."""

        candidates = [
            _map_candidate(normalized_candidate, normalized)
            for term in self._blacklist
            for normalized_candidate in _iter_occurrences(normalized.text, term)
        ]
        return self._select_matches(
            original_text,
            normalized,
            candidates,
            method=method,
        )

    def find_with_whitespace_gaps(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        max_whitespace_gap: int,
    ) -> tuple[Match, ...]:
        """Return bounded space/tab-obfuscated matches at token boundaries."""

        if type(max_whitespace_gap) is not int or max_whitespace_gap <= 0:
            raise ValueError("max_whitespace_gap must be a positive integer")
        if self._whitespace_trie is None or " " not in normalized.text:
            return ()

        candidates = [
            _map_candidate(normalized_candidate, normalized)
            for normalized_candidate in _iter_whitespace_gap_occurrences(
                original_text,
                normalized,
                self._whitespace_trie,
                max_whitespace_gap,
            )
        ]
        return self._select_matches(
            original_text,
            normalized,
            candidates,
            method=MatchMethod.WHITESPACE,
        )

    def _select_matches(
        self,
        original_text: str,
        normalized: NormalizedText,
        candidates: list[_MappedCandidate],
        *,
        method: MatchMethod,
    ) -> tuple[Match, ...]:
        """Apply whitelist and overlap rules to mapped candidates."""

        protected_normalized = bytearray(len(normalized.text))
        protected_original = bytearray(len(original_text))
        for term in self._whitelist:
            for normalized_candidate in _iter_occurrences(normalized.text, term):
                _occupy(
                    _map_candidate(normalized_candidate, normalized),
                    protected_normalized,
                    protected_original,
                )

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
                    method=method,
                    score=1.0,
                )
            )
        return tuple(matches)
