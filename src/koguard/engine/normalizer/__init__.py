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
_MODERN_ONSETS = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_MODERN_VOWELS = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_MODERN_FINALS = "ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"
_COMPATIBILITY_ONSET_INPUT = re.compile(f"[{_MODERN_ONSETS}]")
_COMPOUND_VOWELS = {
    ("ㅗ", "ㅏ"): "ㅘ",
    ("ㅗ", "ㅐ"): "ㅙ",
    ("ㅗ", "ㅣ"): "ㅚ",
    ("ㅜ", "ㅓ"): "ㅝ",
    ("ㅜ", "ㅔ"): "ㅞ",
    ("ㅜ", "ㅣ"): "ㅟ",
    ("ㅡ", "ㅣ"): "ㅢ",
}
_COMPOUND_FINALS = {
    ("ㄱ", "ㅅ"): "ㄳ",
    ("ㄴ", "ㅈ"): "ㄵ",
    ("ㄴ", "ㅎ"): "ㄶ",
    ("ㄹ", "ㄱ"): "ㄺ",
    ("ㄹ", "ㅁ"): "ㄻ",
    ("ㄹ", "ㅂ"): "ㄼ",
    ("ㄹ", "ㅅ"): "ㄽ",
    ("ㄹ", "ㅌ"): "ㄾ",
    ("ㄹ", "ㅍ"): "ㄿ",
    ("ㄹ", "ㅎ"): "ㅀ",
    ("ㅂ", "ㅅ"): "ㅄ",
}
_DUBEOLSIK_UNSHIFTED = {
    "q": "ㅂ",
    "w": "ㅈ",
    "e": "ㄷ",
    "r": "ㄱ",
    "t": "ㅅ",
    "y": "ㅛ",
    "u": "ㅕ",
    "i": "ㅑ",
    "o": "ㅐ",
    "p": "ㅔ",
    "a": "ㅁ",
    "s": "ㄴ",
    "d": "ㅇ",
    "f": "ㄹ",
    "g": "ㅎ",
    "h": "ㅗ",
    "j": "ㅓ",
    "k": "ㅏ",
    "l": "ㅣ",
    "z": "ㅋ",
    "x": "ㅌ",
    "c": "ㅊ",
    "v": "ㅍ",
    "b": "ㅠ",
    "n": "ㅜ",
    "m": "ㅡ",
}
_DUBEOLSIK_JAMO = {
    **_DUBEOLSIK_UNSHIFTED,
    **{key.upper(): value for key, value in _DUBEOLSIK_UNSHIFTED.items()},
    "Q": "ㅃ",
    "W": "ㅉ",
    "E": "ㄸ",
    "R": "ㄲ",
    "T": "ㅆ",
    "O": "ㅒ",
    "P": "ㅖ",
}
_MODERN_COMPATIBILITY_JAMO = frozenset(_MODERN_ONSETS + _MODERN_VOWELS + _MODERN_FINALS)
_SEGMENTED_CHOSEONG_CHARACTERS = frozenset(_MODERN_ONSETS).union(
    normalize("NFKC", onset) for onset in _MODERN_ONSETS
)


def _is_jamo(character: str) -> bool:
    codepoint = ord(character)
    return (
        0x1100 <= codepoint <= 0x11FF
        or 0x3130 <= codepoint <= 0x318F
        or 0xA960 <= codepoint <= 0xA97F
        or 0xD7B0 <= codepoint <= 0xD7FF
    )


def has_compatibility_choseong_input(text: str) -> bool:
    """Return whether raw input contains a modern compatibility onset."""

    return _COMPATIBILITY_ONSET_INPUT.search(text) is not None


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


def _is_allowed_segmented_gap_character(
    original_text: str,
    normalized: NormalizedText,
    index: int,
    *,
    separators: frozenset[str],
    max_whitespace_gap: int,
) -> bool:
    character = normalized.text[index]
    if character in separators:
        return True
    if character != " ":
        return False
    source_start, source_end = normalized.source_spans[index]
    source_gap = original_text[source_start:source_end]
    return len(source_gap) <= max_whitespace_gap and all(
        source_character in {" ", "\t"} for source_character in source_gap
    )


def _build_segmented_normalized_view(
    original_text: str,
    normalized: NormalizedText,
    *,
    eligible_characters: frozenset[str],
    separators: frozenset[str],
    max_whitespace_gap: int,
) -> NormalizedText:
    """Remove bounded gaps only when both neighboring characters are eligible."""

    if type(max_whitespace_gap) is not int or max_whitespace_gap <= 0:
        raise ValueError("max_whitespace_gap must be a positive integer")
    if eligible_characters.isdisjoint(normalized.text):
        return normalized

    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    changed = False
    index = 0
    while index < len(normalized.text):
        character = normalized.text[index]
        characters.append(character)
        source_spans.append(normalized.source_spans[index])

        if character not in eligible_characters:
            index += 1
            continue

        gap_end = index + 1
        while gap_end < len(normalized.text) and _is_allowed_segmented_gap_character(
            original_text,
            normalized,
            gap_end,
            separators=separators,
            max_whitespace_gap=max_whitespace_gap,
        ):
            gap_end += 1
        if gap_end > index + 1 and (
            gap_end < len(normalized.text) and normalized.text[gap_end] in eligible_characters
        ):
            changed = True
            index = gap_end
            continue
        index += 1

    if not changed:
        return normalized
    return NormalizedText(text="".join(characters), source_spans=tuple(source_spans))


def _raw_segmented_gap_end(
    text: str,
    start: int,
    unicode_form: NormalizationForm,
    *,
    separators: frozenset[str],
    max_whitespace_gap: int,
) -> int:
    """Return the end of one raw bounded gap, or its start when invalid."""

    index = start
    while index < len(text):
        character = text[index]
        if character in {" ", "\t"}:
            whitespace_end = index + 1
            while whitespace_end < len(text) and text[whitespace_end] in {" ", "\t"}:
                whitespace_end += 1
            if whitespace_end - index > max_whitespace_gap:
                return start
            index = whitespace_end
            continue
        normalized_character = normalize(unicode_form, character)
        if len(normalized_character) == 1 and normalized_character in separators:
            index += 1
            continue
        break
    return index if index > start else start


def _compose_jamo_units(
    units: list[tuple[str, tuple[int, int]]],
) -> tuple[list[str], list[tuple[int, int]]]:
    """Compose modern compatibility-jamo keystrokes into Hangul syllables."""

    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    index = 0
    while index < len(units):
        onset, onset_span = units[index]
        if (
            onset not in _MODERN_ONSETS
            or index + 1 >= len(units)
            or units[index + 1][0] not in _MODERN_VOWELS
        ):
            characters.append(onset)
            source_spans.append(onset_span)
            index += 1
            continue

        vowel = units[index + 1][0]
        end = index + 2
        if end < len(units):
            compound_vowel = _COMPOUND_VOWELS.get((vowel, units[end][0]))
            if compound_vowel is not None:
                vowel = compound_vowel
                end += 1

        final = ""
        if end < len(units) and units[end][0] in _MODERN_FINALS:
            first_final = units[end][0]
            followed_by_vowel = end + 1 < len(units) and units[end + 1][0] in _MODERN_VOWELS
            if not followed_by_vowel:
                final = first_final
                end += 1
                if end < len(units):
                    compound_final = _COMPOUND_FINALS.get((final, units[end][0]))
                    second_followed_by_vowel = (
                        end + 1 < len(units) and units[end + 1][0] in _MODERN_VOWELS
                    )
                    if compound_final is not None and not second_followed_by_vowel:
                        final = compound_final
                        end += 1

        onset_index = _MODERN_ONSETS.index(onset)
        vowel_index = _MODERN_VOWELS.index(vowel)
        final_index = 0 if not final else _MODERN_FINALS.index(final) + 1
        characters.append(
            chr(
                _HANGUL_SYLLABLE_BASE
                + (onset_index * _HANGUL_VOWEL_COUNT + vowel_index) * _HANGUL_TRAILING_COUNT
                + final_index
            )
        )
        final_span = units[end - 1][1]
        source_spans.append((onset_span[0], final_span[1]))
        index = end

    return characters, source_spans


def build_dubeolsik_view(normalized: NormalizedText) -> NormalizedText:
    """Map ASCII Dubeolsik keystroke runs to composed Hangul with source spans."""

    if not any(character in _DUBEOLSIK_JAMO for character in normalized.text):
        return normalized

    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    index = 0
    while index < len(normalized.text):
        if normalized.text[index] not in _DUBEOLSIK_JAMO:
            characters.append(normalized.text[index])
            source_spans.append(normalized.source_spans[index])
            index += 1
            continue

        end = index + 1
        while end < len(normalized.text) and normalized.text[end] in _DUBEOLSIK_JAMO:
            end += 1
        composed, composed_spans = _compose_jamo_units(
            [
                (_DUBEOLSIK_JAMO[normalized.text[cursor]], normalized.source_spans[cursor])
                for cursor in range(index, end)
            ]
        )
        characters.extend(composed)
        source_spans.extend(composed_spans)
        index = end

    return NormalizedText(text="".join(characters), source_spans=tuple(source_spans))


def _build_jamo_composition_view(
    text: str,
    unicode_form: NormalizationForm,
    *,
    separators: frozenset[str] | None,
    max_whitespace_gap: int | None,
) -> NormalizedText:
    characters: list[str] = []
    source_spans: list[tuple[int, int]] = []
    index = 0
    while index < len(text):
        if text[index] in _MODERN_COMPATIBILITY_JAMO:
            units: list[tuple[str, tuple[int, int]]] = []
            end = index
            while end < len(text) and text[end] in _MODERN_COMPATIBILITY_JAMO:
                units.append((text[end], (end, end + 1)))
                next_index = end + 1
                if next_index < len(text) and text[next_index] in _MODERN_COMPATIBILITY_JAMO:
                    end = next_index
                    continue
                if separators is None or max_whitespace_gap is None:
                    end = next_index
                    break
                gap_end = _raw_segmented_gap_end(
                    text,
                    next_index,
                    unicode_form,
                    separators=separators,
                    max_whitespace_gap=max_whitespace_gap,
                )
                if gap_end < len(text) and text[gap_end] in _MODERN_COMPATIBILITY_JAMO:
                    end = gap_end
                    continue
                end = next_index
                break
            composed, composed_spans = _compose_jamo_units(units)
            characters.extend(composed)
            source_spans.extend(composed_spans)
            index = end
            continue

        end = index + 1
        while end < len(text) and text[end] not in _MODERN_COMPATIBILITY_JAMO:
            end += 1
        normalized_chunk = normalize_text(text[index:end], unicode_form)
        characters.extend(normalized_chunk.text)
        source_spans.extend(
            (start + index, stop + index) for start, stop in normalized_chunk.source_spans
        )
        index = end

    return NormalizedText(text="".join(characters), source_spans=tuple(source_spans))


def build_jamo_composition_view(
    text: str,
    unicode_form: NormalizationForm,
    *,
    normalized: NormalizedText | None = None,
) -> NormalizedText:
    """Compose raw modern compatibility-jamo runs without changing the base view."""

    base = normalized or normalize_text(text, unicode_form)
    if _MODERN_COMPATIBILITY_JAMO.isdisjoint(text):
        return base
    return _build_jamo_composition_view(
        text,
        unicode_form,
        separators=None,
        max_whitespace_gap=None,
    )


def build_segmented_choseong_view(
    text: str,
    normalized: NormalizedText,
    *,
    separators: frozenset[str],
    max_whitespace_gap: int,
) -> NormalizedText:
    """Join bounded gaps only between normalized modern Hangul initials."""

    return _build_segmented_normalized_view(
        text,
        normalized,
        eligible_characters=_SEGMENTED_CHOSEONG_CHARACTERS,
        separators=separators,
        max_whitespace_gap=max_whitespace_gap,
    )


def build_segmented_dubeolsik_view(
    text: str,
    normalized: NormalizedText,
    *,
    separators: frozenset[str],
    max_whitespace_gap: int,
) -> NormalizedText:
    """Compose Dubeolsik runs after joining only bounded keyboard-input gaps."""

    segmented = _build_segmented_normalized_view(
        text,
        normalized,
        eligible_characters=frozenset(_DUBEOLSIK_JAMO),
        separators=separators,
        max_whitespace_gap=max_whitespace_gap,
    )
    return build_dubeolsik_view(segmented)


def build_segmented_jamo_composition_view(
    text: str,
    unicode_form: NormalizationForm,
    *,
    normalized: NormalizedText | None = None,
    separators: frozenset[str],
    max_whitespace_gap: int,
) -> NormalizedText:
    """Compose compatibility-jamo runs across bounded spaces and separators."""

    if type(max_whitespace_gap) is not int or max_whitespace_gap <= 0:
        raise ValueError("max_whitespace_gap must be a positive integer")
    base = normalized or normalize_text(text, unicode_form)
    if _MODERN_COMPATIBILITY_JAMO.isdisjoint(text):
        return base
    return _build_jamo_composition_view(
        text,
        unicode_form,
        separators=separators,
        max_whitespace_gap=max_whitespace_gap,
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
