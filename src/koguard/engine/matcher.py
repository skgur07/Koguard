"""Low-cost exact matching with span-scoped whitelist protection."""

from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from heapq import heappop, heappush
from types import MappingProxyType

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


@dataclass(frozen=True, slots=True)
class _AutomatonNode:
    children: Mapping[str, int]
    failure: int
    longest_output_term: str | None


@dataclass(frozen=True, slots=True)
class _TermAutomaton:
    nodes: tuple[_AutomatonNode, ...]
    fallback_terms: Mapping[str, str | None]


@dataclass(frozen=True, slots=True)
class _ProtectedMasks:
    normalized: bytes
    original: bytes


@dataclass(frozen=True, slots=True)
class _MixedProjection:
    normalized: NormalizedText
    source: NormalizedText
    source_indexes: tuple[int, ...]
    whitespace_prefix: tuple[int, ...]
    separator_prefix: tuple[int, ...]


@dataclass(order=True, slots=True)
class _PrioritizedCandidate:
    priority: tuple[int, int, str, int, int]
    candidate: _MappedCandidate = field(compare=False)


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
        node = root
        for character in term:
            child = node.children.get(character)
            if child is None:
                child = _TermTrieNode()
                node.children[character] = child
            node = child
        node.term = term
    return root


def _build_term_automaton(terms: tuple[str, ...]) -> _TermAutomaton:
    """Build a reversed Aho-Corasick index for longest matches at each start."""

    children: list[dict[str, int]] = [{}]
    failures = [0]
    terminal_terms: list[str | None] = [None]

    for term in terms:
        state = 0
        for character in reversed(term):
            next_state = children[state].get(character)
            if next_state is None:
                next_state = len(children)
                children[state][character] = next_state
                children.append({})
                failures.append(0)
                terminal_terms.append(None)
            state = next_state
        terminal_terms[state] = term

    longest_outputs: list[str | None] = [None] * len(children)
    pending: deque[int] = deque()
    for state in children[0].values():
        longest_outputs[state] = terminal_terms[state]
        pending.append(state)

    while pending:
        state = pending.popleft()
        for character, next_state in children[state].items():
            failure = failures[state]
            while failure and character not in children[failure]:
                failure = failures[failure]
            failures[next_state] = children[failure].get(character, 0)
            longest_outputs[next_state] = (
                terminal_terms[next_state] or longest_outputs[failures[next_state]]
            )
            pending.append(next_state)

    fallback_terms = {
        term: longest_outputs[failures[state]]
        for state, term in enumerate(terminal_terms)
        if term is not None
    }
    return _TermAutomaton(
        nodes=tuple(
            _AutomatonNode(
                children=MappingProxyType(dict(state_children)),
                failure=failures[state],
                longest_output_term=longest_outputs[state],
            )
            for state, state_children in enumerate(children)
        ),
        fallback_terms=MappingProxyType(fallback_terms),
    )


def _iter_longest_occurrences(
    text: str,
    automaton: _TermAutomaton,
) -> Iterator[_NormalizedCandidate]:
    """Yield at most one longest dictionary occurrence per text start."""

    if not automaton.nodes[0].children:
        return

    state = 0
    for start in range(len(text) - 1, -1, -1):
        character = text[start]
        while state and character not in automaton.nodes[state].children:
            state = automaton.nodes[state].failure
        state = automaton.nodes[state].children.get(character, 0)
        term = automaton.nodes[state].longest_output_term
        if term is not None:
            yield _NormalizedCandidate(
                term=term,
                start=start,
                end=start + len(term),
            )


def _next_shorter_occurrence(
    candidate: _NormalizedCandidate,
    automaton: _TermAutomaton,
) -> _NormalizedCandidate | None:
    """Return the next matching prefix term without rescanning the input."""

    term = automaton.fallback_terms[candidate.term]
    if term is None:
        return None
    return _NormalizedCandidate(
        term=term,
        start=candidate.start,
        end=candidate.start + len(term),
    )


def _build_whitespace_trie(terms: tuple[str, ...]) -> _TermTrieNode:
    eligible_terms = tuple(
        term
        for term in terms
        if len(term) >= 2 and not any(character.isspace() for character in term)
    )
    return _build_term_trie(eligible_terms)


def _build_mixed_automaton(terms: tuple[str, ...]) -> _TermAutomaton:
    eligible_terms = tuple(term for term in terms if len(term) >= 2 and term.isalnum())
    return _build_term_automaton(eligible_terms)


def _build_mixed_projection(
    original_text: str,
    normalized: NormalizedText,
    *,
    max_whitespace_gap: int,
    separators: frozenset[str],
) -> _MixedProjection:
    """Remove bounded spaces/tabs and configured separators in one linear view."""

    allowed_whitespace = _build_allowed_whitespace_gap_mask(
        original_text,
        normalized,
        max_whitespace_gap,
    )
    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    source_indexes: list[int] = []
    whitespace_prefix = [0]
    separator_prefix = [0]
    pending_whitespace = False
    pending_separator = False

    for index in range(len(normalized.text)):
        character = normalized.text[index]
        if character == " " and allowed_whitespace[index]:
            if characters:
                pending_whitespace = True
            continue
        if character in separators:
            if characters:
                pending_separator = True
            continue

        characters.append(character)
        source_spans.append(normalized.source_spans[index])
        source_indexes.append(index)
        whitespace_prefix.append(whitespace_prefix[-1] + int(pending_whitespace))
        separator_prefix.append(separator_prefix[-1] + int(pending_separator))
        pending_whitespace = False
        pending_separator = False

    return _MixedProjection(
        normalized=NormalizedText(
            text="".join(characters),
            source_spans=tuple(source_spans),
        ),
        source=normalized,
        source_indexes=tuple(source_indexes),
        whitespace_prefix=tuple(whitespace_prefix),
        separator_prefix=tuple(separator_prefix),
    )


def _is_mixed_candidate(
    candidate: _NormalizedCandidate,
    projection: _MixedProjection,
) -> bool:
    """Return whether a candidate crosses both gap types at token boundaries."""

    first_boundary = candidate.start + 1
    uses_whitespace = (
        projection.whitespace_prefix[candidate.end] - projection.whitespace_prefix[first_boundary]
        > 0
    )
    uses_separator = (
        projection.separator_prefix[candidate.end] - projection.separator_prefix[first_boundary] > 0
    )
    if not uses_whitespace or not uses_separator:
        return False

    source_start = projection.source_indexes[candidate.start]
    source_end = projection.source_indexes[candidate.end - 1] + 1
    return _has_alphanumeric_boundaries(
        projection.source.text,
        source_start,
        source_end,
    )


def _next_mixed_occurrence(
    candidate: _NormalizedCandidate,
    automaton: _TermAutomaton,
    projection: _MixedProjection,
) -> _NormalizedCandidate | None:
    """Return the next shorter mixed candidate without rescanning the input."""

    next_candidate = _next_shorter_occurrence(candidate, automaton)
    while next_candidate is not None:
        if _is_mixed_candidate(next_candidate, projection):
            return next_candidate
        next_candidate = _next_shorter_occurrence(next_candidate, automaton)
    return None


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


def _overlaps_mask(mask: bytes | bytearray, start: int, end: int) -> bool:
    return mask.find(b"\x01", start, end) >= 0


def _mark_mask(mask: bytearray, start: int, end: int) -> None:
    mask[start:end] = b"\x01" * (end - start)


def _is_occupied(
    candidate: _MappedCandidate,
    normalized_mask: bytes | bytearray,
    original_mask: bytes | bytearray,
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
    normalized_mask: bytes | bytearray,
    original_mask: bytes | bytearray,
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

    __slots__ = (
        "_exact_automaton",
        "_mixed_automaton",
        "_whitelist_automaton",
        "_whitespace_trie",
    )

    def __init__(
        self,
        dictionary: KoguardDictionary,
        *,
        whitespace_gap_matching: bool = True,
    ) -> None:
        blacklist = dictionary.ordered_blacklist
        self._exact_automaton = _build_term_automaton(blacklist)
        self._whitelist_automaton = _build_term_automaton(dictionary.ordered_whitelist)
        self._whitespace_trie = (
            _build_whitespace_trie(blacklist) if whitespace_gap_matching else None
        )
        self._mixed_automaton = (
            _build_mixed_automaton(blacklist) if whitespace_gap_matching else None
        )

    def find(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        method: MatchMethod = MatchMethod.EXACT,
        protected_masks: _ProtectedMasks | None = None,
        protected_original: bytes | None = None,
    ) -> tuple[Match, ...]:
        """Return deterministic, non-overlapping exact matches."""

        return self._select_exact_matches(
            original_text,
            normalized,
            method=method,
            protected_masks=protected_masks,
            protected_original=protected_original,
        )

    def build_protected_masks(
        self,
        original_text: str,
        normalized: NormalizedText,
    ) -> _ProtectedMasks:
        """Return normalized and original positions protected in one view."""

        protected_normalized = bytearray(len(normalized.text))
        protected_original = bytearray(len(original_text))
        for normalized_candidate in _iter_longest_occurrences(
            normalized.text,
            self._whitelist_automaton,
        ):
            _occupy(
                _map_candidate(normalized_candidate, normalized),
                protected_normalized,
                protected_original,
            )
        return _ProtectedMasks(
            normalized=bytes(protected_normalized),
            original=bytes(protected_original),
        )

    def build_protected_original_mask(
        self,
        original_text: str,
        normalized: NormalizedText,
    ) -> bytes:
        """Return original positions protected by Whitelist terms in one view."""

        return self.build_protected_masks(original_text, normalized).original

    def find_with_whitespace_gaps(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        max_whitespace_gap: int,
        protected_masks: _ProtectedMasks | None = None,
        protected_original: bytes | None = None,
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
            protected_masks=protected_masks,
            protected_original=protected_original,
        )

    def find_with_mixed_gaps(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        max_whitespace_gap: int,
        separators: frozenset[str],
        protected_original: bytes | None = None,
    ) -> tuple[Match, ...]:
        """Return matches obfuscated with both spaces/tabs and separators."""

        if type(max_whitespace_gap) is not int or max_whitespace_gap <= 0:
            raise ValueError("max_whitespace_gap must be a positive integer")
        if (
            self._mixed_automaton is None
            or not separators
            or " " not in normalized.text
            or separators.isdisjoint(normalized.text)
        ):
            return ()

        projection = _build_mixed_projection(
            original_text,
            normalized,
            max_whitespace_gap=max_whitespace_gap,
            separators=separators,
        )
        if projection.whitespace_prefix[-1] == 0 or projection.separator_prefix[-1] == 0:
            return ()

        resolved_protected_original = (
            self.build_protected_masks(original_text, normalized).original
            if protected_original is None
            else protected_original
        )
        return self._select_mixed_matches(
            original_text,
            projection,
            protected_original=resolved_protected_original,
        )

    def _select_exact_matches(
        self,
        original_text: str,
        normalized: NormalizedText,
        *,
        method: MatchMethod,
        protected_masks: _ProtectedMasks | None,
        protected_original: bytes | None,
    ) -> tuple[Match, ...]:
        """Select exact matches while keeping at most one candidate per start."""

        resolved_protected_masks = protected_masks or self.build_protected_masks(
            original_text, normalized
        )
        resolved_protected_original = (
            resolved_protected_masks.original if protected_original is None else protected_original
        )
        selected_normalized = bytearray(len(normalized.text))
        selected_original = bytearray(len(original_text))
        selected: list[_MappedCandidate] = []
        candidates: list[_PrioritizedCandidate] = []

        for normalized_candidate in _iter_longest_occurrences(
            normalized.text,
            self._exact_automaton,
        ):
            heappush(
                candidates,
                _prioritize(_map_candidate(normalized_candidate, normalized)),
            )

        while candidates:
            mapped_candidate = heappop(candidates).candidate
            protected = _is_occupied(
                mapped_candidate,
                resolved_protected_masks.normalized,
                resolved_protected_original,
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
                resolved_protected_masks.normalized,
                resolved_protected_original,
            ) or _is_start_occupied(
                mapped_candidate,
                selected_normalized,
                selected_original,
            ):
                continue

            next_candidate = _next_shorter_occurrence(
                mapped_candidate.normalized,
                self._exact_automaton,
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
        protected_masks: _ProtectedMasks | None,
        protected_original: bytes | None,
    ) -> tuple[Match, ...]:
        if self._whitespace_trie is None:
            return ()

        resolved_protected_masks = protected_masks or self.build_protected_masks(
            original_text, normalized
        )
        resolved_protected_original = (
            resolved_protected_masks.original if protected_original is None else protected_original
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
                resolved_protected_masks.normalized,
                resolved_protected_original,
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
                resolved_protected_masks.normalized,
                resolved_protected_original,
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

    def _select_mixed_matches(
        self,
        original_text: str,
        projection: _MixedProjection,
        *,
        protected_original: bytes,
    ) -> tuple[Match, ...]:
        if self._mixed_automaton is None:
            return ()

        protected_normalized = bytes(len(projection.normalized.text))
        selected_normalized = bytearray(len(projection.normalized.text))
        selected_original = bytearray(len(original_text))
        selected: list[_MappedCandidate] = []
        candidates: list[_PrioritizedCandidate] = []

        for normalized_candidate in _iter_longest_occurrences(
            projection.normalized.text,
            self._mixed_automaton,
        ):
            if _is_mixed_candidate(normalized_candidate, projection):
                heappush(
                    candidates,
                    _prioritize(_map_candidate(normalized_candidate, projection.normalized)),
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

            next_candidate = _next_mixed_occurrence(
                mapped_candidate.normalized,
                self._mixed_automaton,
                projection,
            )
            if next_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(_map_candidate(next_candidate, projection.normalized)),
                )

        return _build_matches(original_text, selected, MatchMethod.MIXED)
