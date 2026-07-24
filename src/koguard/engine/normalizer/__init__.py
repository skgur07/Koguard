"""Minimal Unicode and whitespace normalization with source span tracking."""

from dataclasses import dataclass
from unicodedata import combining, normalize

from koguard.config import NormalizationForm

_JAMO_RANGES = (
    (0x1100, 0x11FF),
    (0x3130, 0x318F),
    (0xA960, 0xA97F),
    (0xD7B0, 0xD7FF),
)


def _is_jamo(character: str) -> bool:
    codepoint = ord(character)
    return any(start <= codepoint <= end for start, end in _JAMO_RANGES)


def _is_variation_selector(character: str) -> bool:
    codepoint = ord(character)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


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
