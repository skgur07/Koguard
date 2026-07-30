"""Tests for Unicode normalization and source span tracking."""

from collections.abc import Callable
from typing import cast
from unicodedata import normalize as unicode_normalize

import pytest

import koguard.engine.normalizer as normalizer_module
from koguard.config import NormalizationForm
from koguard.engine.normalizer import (
    NormalizedText,
    build_repeated_view,
    build_separator_view,
    normalize_text,
)


def test_normalizer_handles_empty_input() -> None:
    normalized = normalize_text("", "NFKC")

    assert normalized.text == ""
    assert normalized.source_spans == ()


def test_normalizer_collapses_whitespace_with_source_span() -> None:
    normalized = normalize_text("A\t \nB", "NFKC")

    assert normalized.text == "A B"
    assert normalized.source_spans == ((0, 1), (1, 4), (4, 5))
    assert normalized.original_span(1, 2) == (1, 4)


def test_normalizer_composes_decomposed_hangul_jamo() -> None:
    normalized = normalize_text("\u1100\u1161", "NFC")

    assert normalized.text == "가"
    assert normalized.source_spans == ((0, 2),)
    assert normalized.original_span(0, 1) == (0, 2)


def test_normalizer_maps_multiple_compatibility_jamo_syllables() -> None:
    normalized = normalize_text("ㄱㅏㄴㅏ", "NFKC")

    assert normalized.text == "가나"
    assert normalized.source_spans == ((0, 2), (2, 4))


def test_normalizer_composes_combining_character() -> None:
    normalized = normalize_text("e\u0301", "NFC")

    assert normalized.text == "é"
    assert normalized.source_spans == ((0, 2),)


def test_normalizer_keeps_reordered_combining_spans_forward() -> None:
    normalized = normalize_text("a\u0315\u0327", "NFC")

    assert normalized.text == "a\u0327\u0315"
    assert normalized.source_spans == ((0, 1), (1, 3), (1, 3))
    assert normalized.original_span(1, 3) == (1, 3)


def test_normalizer_reordered_combining_spans_cover_each_source_character() -> None:
    source = "B\u0315\u0304\u035e\u0348\u0333\u0347\u034b\u0307"

    normalized = normalize_text(source, "NFC")

    assert all(
        left_start <= right_start and left_end <= right_end
        for (left_start, left_end), (right_start, right_end) in zip(
            normalized.source_spans,
            normalized.source_spans[1:],
            strict=False,
        )
    )
    for normalized_index, character in enumerate(normalized.text):
        source_index = source.index(character)
        original_start, original_end = normalized.original_span(
            normalized_index,
            normalized_index + 1,
        )
        assert original_start <= source_index < original_end


def test_normalizer_processes_max_length_combining_cluster_with_linear_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = "e" + "\u0301" * 4095
    expected_text = unicode_normalize("NFC", source)
    normalized_input_length = 0
    real_normalize = cast(
        Callable[[NormalizationForm, str], str],
        vars(normalizer_module)["normalize"],
    )

    def count_normalized_input(form: NormalizationForm, text: str) -> str:
        nonlocal normalized_input_length
        normalized_input_length += len(text)
        return real_normalize(form, text)

    monkeypatch.setattr(normalizer_module, "normalize", count_normalized_input)

    normalized = normalize_text(source, "NFC")

    assert normalized.text == expected_text
    assert normalized.source_spans == ((0, 2),) + tuple(
        (index, index + 1) for index in range(2, len(source))
    )
    assert normalized.original_span(0, len(normalized.text)) == (0, len(source))
    assert normalized_input_length <= len(source) * 2


def test_normalizer_maps_compatibility_expansion_to_one_source_character() -> None:
    normalized = normalize_text("ﬃ", "NFKC")

    assert normalized.text == "ffi"
    assert normalized.source_spans == ((0, 1), (0, 1), (0, 1))


def test_normalizer_skips_unicode_slow_path_for_stable_ascii_and_hangul(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_slow_path(form: str, text: str) -> str:
        raise AssertionError(f"stable text unexpectedly normalized with {form}: {text}")

    monkeypatch.setattr(normalizer_module, "normalize", reject_slow_path)

    normalized = normalize_text("abc한글", "NFKC")

    assert normalized.text == "abc한글"
    assert normalized.source_spans == tuple((index, index + 1) for index in range(5))


def test_repeated_view_removes_repeated_vowel_extension_and_preserves_span() -> None:
    repeated = build_repeated_view(normalize_text("시이이발", "NFKC"), threshold=2)

    assert repeated.text == "시발"
    assert repeated.source_spans == ((0, 3), (3, 4))
    assert repeated.original_span(0, 2) == (0, 4)


def test_repeated_view_keeps_single_vowel_extension() -> None:
    normalized = normalize_text("시이발", "NFKC")

    assert build_repeated_view(normalized, threshold=2) == normalized


def test_separator_view_removes_allowed_run_between_characters_and_preserves_span() -> None:
    separated = build_separator_view(
        normalize_text("시*!발", "NFKC"),
        separators=frozenset({"*", "!"}),
    )

    assert separated.text == "시발"
    assert separated.source_spans == ((0, 3), (3, 4))
    assert separated.original_span(0, 2) == (0, 4)


@pytest.mark.parametrize("text", ["*시발", "시발*", "시 발", "시/발"])
def test_separator_view_keeps_boundaries_whitespace_and_unconfigured_symbols(text: str) -> None:
    normalized = normalize_text(text, "NFKC")

    assert build_separator_view(normalized, separators=frozenset({"*"})) == normalized


def test_normalized_text_rejects_mismatched_mapping() -> None:
    with pytest.raises(ValueError, match="same length"):
        NormalizedText(text="ab", source_spans=((0, 1),))


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (-1, 1),
        (0, 0),
        (1, 1),
        (0, 2),
    ],
)
def test_normalized_text_rejects_invalid_spans(start: int, end: int) -> None:
    normalized = NormalizedText(text="a", source_spans=((0, 1),))

    with pytest.raises(ValueError, match="normalized span"):
        normalized.original_span(start, end)
