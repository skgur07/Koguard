"""Tests for Unicode normalization and source span tracking."""

import pytest

import koguard.engine.normalizer as normalizer_module
from koguard.engine.normalizer import (
    NormalizedText,
    build_repeated_view,
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
