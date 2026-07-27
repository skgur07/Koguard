"""Minimal Unicode and whitespace normalization with source span tracking."""

import re
from dataclasses import dataclass
from unicodedata import combining, normalize

from koguard.config import NormalizationForm

_REPEATED_VOWEL_EXTENSION = re.compile(r"[아야어여오요우유으이애에얘예와워왜웨외위의]{2}")


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


def _is_stable_character(character: str) -> bool:
    """Return whether one character is unchanged by NFC and NFKC."""

    codepoint = ord(character)
    return codepoint < 0x80 or 0xAC00 <= codepoint <= 0xD7A3


def _has_cluster_extension(text: str, start: int) -> bool:
    if start + 1 >= len(text):
        return False
    next_character = text[start + 1]
    return combining(next_character) != 0 or _is_variation_selector(next_character)


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
    while end < len(text):
        character = text[end]
        if combining(character) == 0 and not _is_variation_selector(character):
            break
        end += 1
    return end


def _normalize_cluster(
    source: str,
    source_start: int,
    unicode_form: NormalizationForm,
) -> tuple[str, tuple[tuple[int, int], ...]]:
    normalized = ""
    spans: list[tuple[int, int]] = []

    for relative_end in range(1, len(source) + 1):
        current = normalize(unicode_form, source[:relative_end])
        common_prefix_length = 0
        while (
            common_prefix_length < len(normalized)
            and common_prefix_length < len(current)
            and normalized[common_prefix_length] == current[common_prefix_length]
        ):
            common_prefix_length += 1

        changed_start = source_start + relative_end - 1
        if common_prefix_length < len(spans):
            changed_start = spans[common_prefix_length][0]

        changed_span = (changed_start, source_start + relative_end)
        spans = spans[:common_prefix_length] + [changed_span] * (
            len(current) - common_prefix_length
        )
        normalized = current

    return normalized, tuple(spans)


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
