"""Low-cost exact matching with span-scoped whitelist protection."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from heapq import heappop, heappush

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
class _TermTrieNode:
    children: dict[str, "_TermTrieNode"] = field(default_factory=dict)
    term: str | None = None
    minimum_term_length: int | None = None


@dataclass(order=True, slots=True)
class _PrioritizedCandidate:
    priority: tuple[int, int, str, int, int]
    candidate: _MappedCandidate = field(compare=False)


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


def _build_allowed_whitespace_gap_mask(
    original_text: str,
    normalized: NormalizedText,
    max_whitespace_gap: int,
) -> bytearray:
    mask = bytearray(len(normalized.text))
    for index, character in enumerate(normalized.text):
        if character == " " and _is_allowed_whitespace_gap(
            original_text,
            normalized,
            index,
            max_whitespace_gap,
        ):
            mask[index] = 1
    return mask


def _has_alphanumeric_boundaries(text: str, start: int, end: int) -> bool:
    return (start == 0 or not text[start - 1].isalnum()) and (
        end == len(text) or not text[end].isalnum()
    )


def _build_term_trie(terms: tuple[str, ...]) -> _TermTrieNode:
    root = _TermTrieNode()
    for term in terms:
        term_length = len(term)
        node = root
        if node.minimum_term_length is None or term_length < node.minimum_term_length:
            node.minimum_term_length = term_length
        for character in term:
            child = node.children.get(character)
            if child is None:
                child = _TermTrieNode()
                node.children[character] = child
            node = child
            if node.minimum_term_length is None or term_length < node.minimum_term_length:
                node.minimum_term_length = term_length
        node.term = term
    return root


def _build_whitespace_trie(terms: tuple[str, ...]) -> _TermTrieNode:
    eligible_terms = tuple(
        term
        for term in terms
        if len(term) >= 2 and not any(character.isspace() for character in term)
    )
    return _build_term_trie(eligible_terms)


def _find_longest_exact_occurrence(
    normalized: NormalizedText,
    root: _TermTrieNode,
    start: int,
    *,
    shorter_than: int | None = None,
) -> _NormalizedCandidate | None:
    """Return the longest exact dictionary term at one normalized start."""

    node = root
    cursor = start
    longest_term: str | None = None
    longest_end = 0
    while cursor < len(normalized.text):
        next_node = node.children.get(normalized.text[cursor])
        if next_node is None:
            break
        node = next_node
        cursor += 1
        if shorter_than is not None and cursor - start >= shorter_than:
            break
        if node.term is not None:
            longest_term = node.term
            longest_end = cursor

    if longest_term is None:
        return None
    return _NormalizedCandidate(term=longest_term, start=start, end=longest_end)


def _find_longest_whitespace_gap_occurrence(
    normalized: NormalizedText,
    root: _TermTrieNode,
    allowed_gap_mask: bytearray,
    start: int,
    *,
    shorter_than: int | None = None,
) -> _NormalizedCandidate | None:
    """Return the longest eligible candidate at one normalized start."""

    node = root.children.get(normalized.text[start])
    if node is None:
        return None

    cursor = start + 1
    term_length = 1
    used_gap = False
    longest_term: str | None = None
    longest_end = 0
    while cursor < len(normalized.text):
        if normalized.text[cursor] == " ":
            if not allowed_gap_mask[cursor]:
                break
            used_gap = True
            cursor += 1
        if cursor >= len(normalized.text):
            break

        node = node.children.get(normalized.text[cursor])
        if node is None:
            break
        cursor += 1
        term_length += 1
        if shorter_than is not None and term_length >= shorter_than:
            break
        if (
            node.term is not None
            and used_gap
            and _has_alphanumeric_boundaries(normalized.text, start, cursor)
        ):
            longest_term = node.term
            longest_end = cursor

    if longest_term is None:
        return None
    return _NormalizedCandidate(term=longest_term, start=start, end=longest_end)


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


def _is_start_occupied(
    candidate: _MappedCandidate,
    normalized_mask: bytearray,
    original_mask: bytearray,
) -> bool:
    return bool(
        normalized_mask[candidate.normalized.start] or original_mask[candidate.original_start]
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


def _prioritize(candidate: _MappedCandidate) -> _PrioritizedCandidate:
    return _PrioritizedCandidate(
        priority=(
            -candidate.length,
            candidate.original_start,
            candidate.normalized.term,
            candidate.normalized.start,
            candidate.original_end,
        ),
        candidate=candidate,
    )


def _build_matches(
    original_text: str,
    selected: list[_MappedCandidate],
    method: MatchMethod,
) -> tuple[Match, ...]:
    return tuple(
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
        for mapped_candidate in sorted(
            selected,
            key=lambda item: (
                item.original_start,
                item.original_end,
                item.normalized.term,
            ),
        )
    )


class ExactMatcher:
    """Find normalized terms and remove protected or overlapping spans."""

    __slots__ = ("_blacklist", "_exact_trie", "_whitelist", "_whitespace_trie")

    def __init__(
        self,
        dictionary: KoguardDictionary,
        *,
        whitespace_gap_matching: bool = True,
    ) -> None:
        self._blacklist = dictionary.ordered_blacklist
        self._whitelist = dictionary.ordered_whitelist
        self._exact_trie = _build_term_trie(self._blacklist)
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

        return self._select_exact_matches(
            original_text,
            normalized,
            method=method,
        )

    def build_protected_original_mask(
        self,
        original_text: str,
        normalized: NormalizedText,
    ) -> bytes:
        """Return original positions protected by Whitelist terms in one view."""

        protected_original = bytearray(len(original_text))
        for mapped_candidate in self._iter_protected_candidates(normalized):
            _mark_mask(
                protected_original,
                mapped_candidate.original_start,
                mapped_candidate.original_end,
            )
        return bytes(protected_original)

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

        return self._select_whitespace_matches(
            original_text,
            normalized,
            max_whitespace_gap=max_whitespace_gap,
        )

    def _build_protected_masks(
        self,
        original_text: str,
        normalized: NormalizedText,
    ) -> tuple[bytearray, bytearray]:
        protected_normalized = bytearray(len(normalized.text))
        protected_original = bytearray(len(original_text))
        for mapped_candidate in self._iter_protected_candidates(normalized):
            _occupy(
                mapped_candidate,
                protected_normalized,
                protected_original,
            )
        return protected_normalized, protected_original

    def _iter_protected_candidates(
        self,
        normalized: NormalizedText,
    ) -> Iterator[_MappedCandidate]:
        for term in self._whitelist:
            for normalized_candidate in _iter_occurrences(normalized.text, term):
                yield _map_candidate(normalized_candidate, normalized)

    def _select_exact_matches(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        method: MatchMethod,
    ) -> tuple[Match, ...]:
        """Select exact matches while keeping at most one candidate per start."""

        protected_normalized, protected_original = self._build_protected_masks(
            original_text,
            normalized,
        )
        selected_normalized = bytearray(len(normalized.text))
        selected_original = bytearray(len(original_text))
        selected: list[_MappedCandidate] = []
        candidates: list[_PrioritizedCandidate] = []

        for start in range(len(normalized.text)):
            first_node = self._exact_trie.children.get(normalized.text[start])
            if first_node is None:
                continue
            minimum_term_length = first_node.minimum_term_length
            if minimum_term_length is None or len(normalized.text) - start < minimum_term_length:
                continue
            normalized_candidate = _find_longest_exact_occurrence(
                normalized,
                self._exact_trie,
                start,
            )
            if normalized_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(_map_candidate(normalized_candidate, normalized)),
                )

        while candidates:
            mapped_candidate = heappop(candidates).candidate
            protected = _is_occupied(
                mapped_candidate,
                protected_normalized,
                protected_original,
            )
            overlaps_selected = _is_occupied(
                mapped_candidate,
                selected_normalized,
                selected_original,
            )
            if not protected and not overlaps_selected:
                selected.append(mapped_candidate)
                _occupy(mapped_candidate, selected_normalized, selected_original)
                continue

            if _is_start_occupied(
                mapped_candidate,
                protected_normalized,
                protected_original,
            ) or _is_start_occupied(
                mapped_candidate,
                selected_normalized,
                selected_original,
            ):
                continue

            next_candidate = _find_longest_exact_occurrence(
                normalized,
                self._exact_trie,
                mapped_candidate.normalized.start,
                shorter_than=mapped_candidate.length,
            )
            if next_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(_map_candidate(next_candidate, normalized)),
                )

        return _build_matches(original_text, selected, method)

    def _select_whitespace_matches(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        max_whitespace_gap: int,
    ) -> tuple[Match, ...]:
        if self._whitespace_trie is None:
            return ()

        protected_normalized, protected_original = self._build_protected_masks(
            original_text,
            normalized,
        )
        selected_normalized = bytearray(len(normalized.text))
        selected_original = bytearray(len(original_text))
        selected: list[_MappedCandidate] = []
        candidates: list[_PrioritizedCandidate] = []
        allowed_gap_mask = _build_allowed_whitespace_gap_mask(
            original_text,
            normalized,
            max_whitespace_gap,
        )

        for start in range(len(normalized.text)):
            normalized_candidate = _find_longest_whitespace_gap_occurrence(
                normalized,
                self._whitespace_trie,
                allowed_gap_mask,
                start,
            )
            if normalized_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(_map_candidate(normalized_candidate, normalized)),
                )

        while candidates:
            mapped_candidate = heappop(candidates).candidate
            protected = _is_occupied(
                mapped_candidate,
                protected_normalized,
                protected_original,
            )
            overlaps_selected = _is_occupied(
                mapped_candidate,
                selected_normalized,
                selected_original,
            )
            if not protected and not overlaps_selected:
                selected.append(mapped_candidate)
                _occupy(mapped_candidate, selected_normalized, selected_original)
                continue

            if _is_start_occupied(
                mapped_candidate,
                protected_normalized,
                protected_original,
            ) or _is_start_occupied(
                mapped_candidate,
                selected_normalized,
                selected_original,
            ):
                continue

            next_candidate = _find_longest_whitespace_gap_occurrence(
                normalized,
                self._whitespace_trie,
                allowed_gap_mask,
                mapped_candidate.normalized.start,
                shorter_than=mapped_candidate.length,
            )
            if next_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(_map_candidate(next_candidate, normalized)),
                )

        return _build_matches(original_text, selected, MatchMethod.WHITESPACE)
