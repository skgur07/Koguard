"""Minimal Unicode and whitespace normalization with source span tracking."""

import re
from dataclasses import dataclass
from unicodedata import category, combining, decomposition, normalize

from koguard.config import NormalizationForm

_REPEATED_VOWEL_EXTENSION = re.compile(r"[아야어여오요우유으이애에얘예와워왜웨외위의]{2}")
_HANGUL_SYLLABLE_BASE = 0xAC00
_HANGUL_SYLLABLE_COUNT = 11172
_HANGUL_LEADING_BASE = 0x1100
_HANGUL_VOWEL_BASE = 0x1161
_HANGUL_TRAILING_BASE = 0x11A7
_HANGUL_VOWEL_COUNT = 21
_HANGUL_TRAILING_COUNT = 28
_HANGUL_N_COUNT = _HANGUL_VOWEL_COUNT * _HANGUL_TRAILING_COUNT


def _is_jamo(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
        or 0xA960 <= codepoint <= 0xA97F
        or 0xD7B0 <= codepoint <= 0xD7FF
    )


def _is_variation_selector(character: str) -> bool:
    codepoint = ord(character)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


def _is_unicode_cluster_extension(character: str) -> bool:
    """Return whether one code point extends the preceding grapheme base."""

    return category(character).startswith("M") or _is_variation_selector(character)


def _is_stable_character(character: str) -> bool:
    """Return whether one character is unchanged by NFC and NFKC."""

    codepoint = ord(character)
    return codepoint < 0x80 or 0xAC00 <= codepoint <= 0xD7A3


def _has_cluster_extension(text: str, start: int) -> bool:
    if start + 1 >= len(text):
        return False
    return _is_unicode_cluster_extension(text[start + 1])


def _cluster_end(text: str, start: int) -> int:
    if text[start].isspace():
        end = start + 1
        while end < len(text) and text[end].isspace():
            end += 1
        return end

    if _is_jamo(text[start]):
        end = start + 1
        while end < len(text) and _is_jamo(text[end]):
            end += 1
        return end

    end = start + 1
    while end < len(text) and _is_unicode_cluster_extension(text[end]):
        end += 1
    return end


def _normalize_cluster(
    source: str,
    source_start: int,
    unicode_form: NormalizationForm,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    normalized = normalize(unicode_form, source)
    compatibility = unicode_form == "NFKC"
    source_decomposition = _decompose_with_origins(source, compatibility=compatibility)
    normalized_decomposition = _decompose_with_origins(
        normalized,
        compatibility=compatibility,
    )

    if [character for character, _ in source_decomposition] != [
        character for character, _ in normalized_decomposition
    ]:
        full_span = (source_start, source_start + len(source))
        return normalized, (full_span,) * len(normalized)

    source_indexes_by_output: list[list[int]] = [[] for _ in normalized]
    for (_, source_index), (_, output_index) in zip(
        source_decomposition,
        normalized_decomposition,
        strict=True,
    ):
        source_indexes_by_output[output_index].append(source_index)

    spans = tuple(
        (
            source_start + min(source_indexes),
            source_start + max(source_indexes) + 1,
        )
        for source_indexes in source_indexes_by_output
    )
    return normalized, _make_spans_monotonic(spans)


def _make_spans_monotonic(
    spans: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, int], ...]:
    """Widen reordered origins so every normalized range maps forward."""

    starts = [start for start, _ in spans]
    ends = [end for _, end in spans]

    for index in range(len(starts) - 2, -1, -1):
        starts[index] = min(starts[index], starts[index + 1])
    for index in range(1, len(ends)):
        ends[index] = max(ends[index], ends[index - 1])

    return tuple(zip(starts, ends, strict=True))


def _decompose_character(
    character: str,
    *,
    compatibility: bool,
) -> tuple[str, ...]:
    codepoint = ord(character)
    syllable_index = codepoint - _HANGUL_SYLLABLE_BASE
    if 0 <= syllable_index < _HANGUL_SYLLABLE_COUNT:
        leading = chr(_HANGUL_LEADING_BASE + syllable_index // _HANGUL_N_COUNT)
        vowel = chr(
            _HANGUL_VOWEL_BASE + (syllable_index % _HANGUL_N_COUNT) // _HANGUL_TRAILING_COUNT
        )
        trailing_index = syllable_index % _HANGUL_TRAILING_COUNT
        if trailing_index == 0:
            return leading, vowel
        return leading, vowel, chr(_HANGUL_TRAILING_BASE + trailing_index)

    mapping = decomposition(character)
    if not mapping:
        return (character,)

    codepoints = mapping.split()
    if codepoints[0].startswith("<"):
        if not compatibility:
            return (character,)
        codepoints = codepoints[1:]

    decomposed: list[str] = []
    for mapped_codepoint in codepoints:
        decomposed.extend(
            _decompose_character(
                chr(int(mapped_codepoint, 16)),
                compatibility=compatibility,
            )
        )
    return tuple(decomposed)


def _decompose_with_origins(
    text: str,
    *,
    compatibility: bool,
) -> list[tuple[str, int]]:
    decomposed = [
        (decomposed_character, index)
        for index, character in enumerate(text)
        for decomposed_character in _decompose_character(
            character,
            compatibility=compatibility,
        )
    ]
    return _canonical_order(decomposed)


def _canonical_order(items: list[tuple[str, int]]) -> list[tuple[str, int]]:
    ordered: list[tuple[str, int]] = []
    combining_run: list[tuple[str, int]] = []

    for item in items:
        if combining(item[0]) == 0:
            ordered.extend(sorted(combining_run, key=lambda candidate: combining(candidate[0])))
            combining_run.clear()
            ordered.append(item)
        else:
            combining_run.append(item)

    ordered.extend(sorted(combining_run, key=lambda candidate: combining(candidate[0])))
    return ordered


@dataclass(frozen=True, slots=True)
class NormalizedText:
    """Normalized text and the original span represented by each character."""

    text: str
    source_spans: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        if len(self.text) != len(self.source_spans):
            raise ValueError("text and source_spans must have the same length")

    def original_span(self, start: int, end: int) -> tuple[int, int]:
        """Map a non-empty normalized span back to the original input."""

        if start < 0 or end > len(self.text) or start >= end:
            raise ValueError("normalized span must satisfy 0 <= start < end <= text length")
        return self.source_spans[start][0], self.source_spans[end - 1][1]


def normalize_text(text: str, unicode_form: NormalizationForm) -> NormalizedText:
    """Normalize Unicode clusters and collapse each whitespace run to one space."""

    normalized_parts: list[str] = []
    source_spans: list[tuple[int, int]] = []
    start = 0

    while start < len(text):
        character = text[start]
        if (
            not character.isspace()
            and _is_stable_character(character)
            and not _has_cluster_extension(text, start)
        ):
            normalized_parts.append(character)
            source_spans.append((start, start + 1))
            start += 1
            continue

        end = _cluster_end(text, start)
        source = text[start:end]
        cluster_spans: tuple[tuple[int, int], ...]
        if source[0].isspace():
            normalized_cluster = " "
            cluster_spans = ((start, end),)
        else:
            normalized_cluster, cluster_spans = _normalize_cluster(
                source,
                start,
                unicode_form,
            )

        normalized_parts.append(normalized_cluster)
        source_spans.extend(cluster_spans)
        start = end

    return NormalizedText(
        text="".join(normalized_parts),
        source_spans=tuple(source_spans),
    )


def _hangul_vowel_index(character: str) -> int | None:
    codepoint = ord(character)
    if not 0xAC00 <= codepoint <= 0xD7A3:
        return None
    return ((codepoint - 0xAC00) % 588) // 28


def _is_standalone_vowel_extension(character: str, vowel_index: int) -> bool:
    codepoint = ord(character)
    if not 0xAC00 <= codepoint <= 0xD7A3:
        return False
    syllable_index = codepoint - 0xAC00
    onset_index = syllable_index // 588
    character_vowel_index = (syllable_index % 588) // 28
    final_index = syllable_index % 28
    return onset_index == 11 and character_vowel_index == vowel_index and final_index == 0


def build_repeated_view(
    normalized: NormalizedText,
    *,
    threshold: int,
) -> NormalizedText:
    """Remove repeated standalone Hangul vowel extensions from an extra view."""

    if type(threshold) is not int or threshold < 2:
        raise ValueError("threshold must be an integer greater than or equal to 2")
    if _REPEATED_VOWEL_EXTENSION.search(normalized.text) is None:
        return normalized

    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    index = 0
    while index < len(normalized.text):
        character = normalized.text[index]
        previous_vowel = _hangul_vowel_index(characters[-1]) if characters else None
        run_end = index + 1
        while run_end < len(normalized.text) and normalized.text[run_end] == character:
            run_end += 1

        if (
            previous_vowel is not None
            and run_end - index >= threshold
            and _is_standalone_vowel_extension(character, previous_vowel)
        ):
            previous_start, _ = source_spans[-1]
            source_spans[-1] = (
                previous_start,
                normalized.source_spans[run_end - 1][1],
            )
            index = run_end
            continue

        characters.append(character)
        source_spans.append(normalized.source_spans[index])
        index += 1

    return NormalizedText(text="".join(characters), source_spans=tuple(source_spans))


def build_separator_view(
    normalized: NormalizedText,
    *,
    separators: frozenset[str],
) -> NormalizedText:
    """Remove configured separator runs between alphanumeric characters."""

    if not separators or separators.isdisjoint(normalized.text):
        return normalized

    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    index = 0
    while index < len(normalized.text):
        character = normalized.text[index]
        if character not in separators:
            characters.append(character)
            source_spans.append(normalized.source_spans[index])
            index += 1
            continue

        run_end = index + 1
        while run_end < len(normalized.text) and normalized.text[run_end] in separators:
            run_end += 1

        if (
            characters
            and characters[-1].isalnum()
            and run_end < len(normalized.text)
            and normalized.text[run_end].isalnum()
        ):
            previous_start, _ = source_spans[-1]
            source_spans[-1] = (
                previous_start,
                normalized.source_spans[run_end - 1][1],
            )
            index = run_end
            continue

        characters.extend(normalized.text[index:run_end])
        source_spans.extend(normalized.source_spans[index:run_end])
        index = run_end

    return NormalizedText(text="".join(characters), source_spans=tuple(source_spans))
