"""Low-cost exact matching with span-scoped whitelist protection."""

from collections import deque
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from heapq import heappop, heappush
from types import MappingProxyType

from koguard.engine.dictionary import KoguardDictionary
from koguard.engine.normalizer import NormalizedText, _is_unicode_cluster_extension
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


@dataclass(slots=True)
class _FallbackNavigator:
    """Resolve length-bounded fallback ancestors with a per-check jump cache."""

    automaton: _TermAutomaton
    jumps: dict[tuple[str, int], str | None] = field(default_factory=dict)

    def longest_not_longer_than(self, term: str, maximum_length: int) -> str | None:
        """Return the longest fallback ancestor within one length bound."""

        if len(term) <= maximum_length:
            return term

        current = term
        for power in range(len(term).bit_length() - 1, -1, -1):
            ancestor = self._jump(current, power)
            if ancestor is not None and len(ancestor) > maximum_length:
                current = ancestor

        return self._jump(current, 0)

    def _jump(self, term: str, power: int) -> str | None:
        key = (term, power)
        if key in self.jumps:
            return self.jumps[key]

        if power == 0:
            ancestor = self.automaton.fallback_terms[term]
        else:
            midpoint = self._jump(term, power - 1)
            ancestor = None if midpoint is None else self._jump(midpoint, power - 1)
        self.jumps[key] = ancestor
        return ancestor


@dataclass(frozen=True, slots=True)
class _ProtectedMasks:
    normalized: bytes
    original: bytes


@dataclass(frozen=True, slots=True)
class _AlphanumericBoundaries:
    starts: bytes
    ends: bytes
    extension_ends: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class _MixedProjection:
    normalized: NormalizedText
    source: NormalizedText
    source_indexes: tuple[int, ...]
    whitespace_prefix: tuple[int, ...]
    separator_prefix: tuple[int, ...]
    source_boundaries: _AlphanumericBoundaries
    previous_end_boundary: tuple[int, ...]
    extension_ends: tuple[int, ...]


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


def _build_alphanumeric_boundaries(text: str) -> _AlphanumericBoundaries:
    """Build cluster-aware token-boundary masks in linear time."""

    starts = bytearray(len(text) + 1)
    starts[0] = 1
    cluster_extensions = bytearray(len(text))
    alphanumeric = bytearray(len(text))
    previous_base_is_alphanumeric = False
    for boundary, character in enumerate(text, start=1):
        is_extension = _is_unicode_cluster_extension(character)
        cluster_extensions[boundary - 1] = is_extension
        if not is_extension:
            previous_base_is_alphanumeric = character.isalnum()
            alphanumeric[boundary - 1] = previous_base_is_alphanumeric
        starts[boundary] = not previous_base_is_alphanumeric

    ends = bytearray(len(text) + 1)
    ends[-1] = 1
    next_base_is_alphanumeric = False
    for boundary in range(len(text) - 1, -1, -1):
        if not cluster_extensions[boundary]:
            next_base_is_alphanumeric = bool(alphanumeric[boundary])
        ends[boundary] = not next_base_is_alphanumeric

    extension_ends = list(range(len(text) + 1))
    for boundary in range(len(text) - 1, -1, -1):
        if cluster_extensions[boundary]:
            extension_ends[boundary] = extension_ends[boundary + 1]

    return _AlphanumericBoundaries(
        starts=bytes(starts),
        ends=bytes(ends),
        extension_ends=tuple(extension_ends),
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
    source_boundaries = _build_alphanumeric_boundaries(normalized.text)

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

    previous_end_boundary = [0]
    latest_end_boundary = 0
    for projected_end, source_index in enumerate(source_indexes, start=1):
        if source_boundaries.ends[source_index + 1]:
            latest_end_boundary = projected_end
        previous_end_boundary.append(latest_end_boundary)

    projected_text = "".join(characters)
    return _MixedProjection(
        normalized=NormalizedText(
            text=projected_text,
            source_spans=tuple(source_spans),
        ),
        source=normalized,
        source_indexes=tuple(source_indexes),
        whitespace_prefix=tuple(whitespace_prefix),
        separator_prefix=tuple(separator_prefix),
        source_boundaries=source_boundaries,
        previous_end_boundary=tuple(previous_end_boundary),
        extension_ends=_build_alphanumeric_boundaries(projected_text).extension_ends,
    )


def _uses_mixed_gaps(
    candidate: _NormalizedCandidate,
    projection: _MixedProjection,
) -> bool:
    """Return whether a candidate crosses both whitespace and separator gaps."""

    first_boundary = candidate.start + 1
    uses_whitespace = (
        projection.whitespace_prefix[candidate.end] - projection.whitespace_prefix[first_boundary]
        > 0
    )
    uses_separator = (
        projection.separator_prefix[candidate.end] - projection.separator_prefix[first_boundary] > 0
    )
    return uses_whitespace and uses_separator


def _has_mixed_start_boundary(
    candidate: _NormalizedCandidate,
    projection: _MixedProjection,
) -> bool:
    """Return whether a projected candidate starts at a source-view boundary."""

    source_start = projection.source_indexes[candidate.start]
    return bool(projection.source_boundaries.starts[source_start])


def _has_mixed_end_boundary(
    candidate: _NormalizedCandidate,
    projection: _MixedProjection,
) -> bool:
    """Return whether a projected candidate ends at a source-view boundary."""

    source_end = projection.source_indexes[candidate.end - 1] + 1
    return bool(projection.source_boundaries.ends[source_end])


def _next_mixed_occurrence(
    candidate: _NormalizedCandidate,
    navigator: _FallbackNavigator,
    projection: _MixedProjection,
) -> _NormalizedCandidate | None:
    """Return the next shorter mixed candidate without a linear fallback scan."""

    if not _has_mixed_start_boundary(candidate, projection):
        return None

    maximum_end = candidate.end - 1
    while maximum_end > candidate.start:
        boundary_end = projection.previous_end_boundary[maximum_end]
        if boundary_end <= candidate.start:
            return None
        maximum_length = boundary_end - candidate.start
        term = navigator.longest_not_longer_than(candidate.term, maximum_length)
        if term is None:
            return None
        next_candidate = _NormalizedCandidate(
            term=term,
            start=candidate.start,
            end=candidate.start + len(term),
        )
        if not _uses_mixed_gaps(next_candidate, projection):
            return None
        if _has_mixed_end_boundary(next_candidate, projection):
            return next_candidate
        maximum_end = next_candidate.end - 1
    return None


def _first_mixed_occurrence(
    candidate: _NormalizedCandidate,
    navigator: _FallbackNavigator,
    projection: _MixedProjection,
) -> _NormalizedCandidate | None:
    """Return the longest valid mixed candidate in one start's fallback chain."""

    if not _uses_mixed_gaps(candidate, projection) or not _has_mixed_start_boundary(
        candidate,
        projection,
    ):
        return None
    if _has_mixed_end_boundary(candidate, projection):
        return candidate
    return _next_mixed_occurrence(candidate, navigator, projection)


def _find_longest_whitespace_gap_occurrence(
    normalized: NormalizedText,
    root: _TermTrieNode,
    allowed_gap_mask: bytearray,
    boundaries: _AlphanumericBoundaries,
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
            and boundaries.starts[start]
            and boundaries.ends[cursor]
        ):
            longest_term = node.term
            longest_end = cursor

    if longest_term is None:
        return None
    return _NormalizedCandidate(term=longest_term, start=start, end=longest_end)


def _map_candidate(
    candidate: _NormalizedCandidate,
    normalized: NormalizedText,
    *,
    extension_ends: tuple[int, ...] | None = None,
) -> _MappedCandidate:
    normalized_end = candidate.end if extension_ends is None else extension_ends[candidate.end]
    original_start, original_end = normalized.original_span(
        candidate.start,
        normalized_end,
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
        occupied_original: bytes | None = None,
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
            occupied_original=occupied_original,
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
        boundaries = _build_alphanumeric_boundaries(normalized.text)

        for start in range(len(normalized.text)):
            normalized_candidate = _find_longest_whitespace_gap_occurrence(
                normalized,
                self._whitespace_trie,
                allowed_gap_mask,
                boundaries,
                start,
            )
            if normalized_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(
                        _map_candidate(
                            normalized_candidate,
                            normalized,
                            extension_ends=boundaries.extension_ends,
                        )
                    ),
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
                boundaries,
                mapped_candidate.normalized.start,
                shorter_than=mapped_candidate.length,
            )
            if next_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(
                        _map_candidate(
                            next_candidate,
                            normalized,
                            extension_ends=boundaries.extension_ends,
                        )
                    ),
                )

        return _build_matches(original_text, selected, MatchMethod.WHITESPACE)

    def _select_mixed_matches(
        self,
        original_text: str,
        projection: _MixedProjection,
        *,
        protected_original: bytes,
        occupied_original: bytes | None,
    ) -> tuple[Match, ...]:
        if self._mixed_automaton is None:
            return ()

        protected_normalized = bytes(len(projection.normalized.text))
        selected_normalized = bytearray(len(projection.normalized.text))
        selected_original = (
            bytearray(len(original_text))
            if occupied_original is None
            else bytearray(occupied_original)
        )
        selected: list[_MappedCandidate] = []
        candidates: list[_PrioritizedCandidate] = []
        navigator = _FallbackNavigator(self._mixed_automaton)

        for normalized_candidate in _iter_longest_occurrences(
            projection.normalized.text,
            self._mixed_automaton,
        ):
            mixed_candidate = _first_mixed_occurrence(
                normalized_candidate,
                navigator,
                projection,
            )
            if mixed_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(
                        _map_candidate(
                            mixed_candidate,
                            projection.normalized,
                            extension_ends=projection.extension_ends,
                        )
                    ),
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
                navigator,
                projection,
            )
            if next_candidate is not None:
                heappush(
                    candidates,
                    _prioritize(
                        _map_candidate(
                            next_candidate,
                            projection.normalized,
                            extension_ends=projection.extension_ends,
                        )
                    ),
                )

        return _build_matches(original_text, selected, MatchMethod.MIXED)
