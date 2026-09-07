"""Correctness tests for the code-point fast paths used by normalization.

These guard optimizations that skip a `unicodedata` table lookup for ranges that
dominate Korean chat. If a future Unicode revision ever puts a combining mark in
one of those ranges, these tests fail instead of the engine silently mis-slicing
grapheme clusters.
"""

from unicodedata import category

from koguard.engine.normalizer import _is_unicode_cluster_extension


def _reference_is_cluster_extension(character: str) -> bool:
    """The unoptimized definition, kept here as the oracle."""

    codepoint = ord(character)
    is_variation_selector = 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF
    return category(character).startswith("M") or is_variation_selector


def test_fast_path_agrees_with_the_reference_across_the_basic_plane() -> None:
    mismatches = [
        hex(codepoint)
        for codepoint in range(0x11000)
        if _is_unicode_cluster_extension(chr(codepoint))
        != _reference_is_cluster_extension(chr(codepoint))
    ]

    assert mismatches == []


def test_fast_path_agrees_with_the_reference_on_variation_selector_supplement() -> None:
    mismatches = [
        hex(codepoint)
        for codepoint in range(0xE0000, 0xE0200)
        if _is_unicode_cluster_extension(chr(codepoint))
        != _reference_is_cluster_extension(chr(codepoint))
    ]

    assert mismatches == []


def test_no_combining_mark_hides_in_the_skipped_ranges() -> None:
    """The ranges the fast path returns False for must stay free of marks."""

    assert not any(category(chr(codepoint)).startswith("M") for codepoint in range(0x0300))
    assert not any(category(chr(codepoint)).startswith("M") for codepoint in range(0xAC00, 0xD7A4))


def test_known_cluster_extensions_are_still_detected() -> None:
    assert _is_unicode_cluster_extension("\u0301") is True  # combining acute
    assert _is_unicode_cluster_extension("\ufe0f") is True  # variation selector-16
    assert _is_unicode_cluster_extension("\U000e0101") is True  # variation selector-18
    assert _is_unicode_cluster_extension("가") is False
    assert _is_unicode_cluster_extension("a") is False
    assert _is_unicode_cluster_extension(" ") is False
