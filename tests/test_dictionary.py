"""Tests for immutable dictionary loading."""

from pathlib import Path
from typing import cast

import pytest

from koguard import DictionaryError, KoguardDictionary


def test_default_dictionary_loads_bundled_terms() -> None:
    dictionary = KoguardDictionary.default()

    assert {
        "병신",
        "시발",
        "씨발",
        "개새끼",
        "좆같다",
        "지랄",
        "염병",
        "꺼져",
    } <= dictionary.blacklist
    assert len(dictionary.blacklist) >= 30
    assert "병신년" not in dictionary.whitelist
    assert "시발점" not in dictionary.whitelist


def test_dictionary_normalizes_deduplicates_and_skips_comments() -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["ＡＢ", "AB", "", "  # 설명"],
        whitelist=["ＡＢＣ"],
        include_defaults=False,
    )

    assert dictionary.blacklist == frozenset({"AB"})
    assert dictionary.whitelist == frozenset({"ABC"})


def test_dictionary_extends_packaged_data_by_default() -> None:
    dictionary = KoguardDictionary.from_sources(blacklist=["금칙어"])

    assert {"병신", "금칙어"} <= dictionary.blacklist


def test_dictionary_loads_utf8_files(tmp_path: Path) -> None:
    blacklist_path = tmp_path / "blacklist.txt"
    whitelist_path = tmp_path / "whitelist.txt"
    blacklist_path.write_text("긴금칙어\n금칙어\n", encoding="utf-8")
    whitelist_path.write_text("정상 표현\n", encoding="utf-8")

    dictionary = KoguardDictionary.from_sources(
        blacklist_path=blacklist_path,
        whitelist_path=whitelist_path,
        include_defaults=False,
    )

    assert dictionary.ordered_blacklist == ("긴금칙어", "금칙어")
    assert dictionary.ordered_whitelist == ("정상 표현",)


def test_dictionary_rejects_non_string_entries() -> None:
    invalid_entries = cast(list[str], [1])

    with pytest.raises(DictionaryError, match="must be strings"):
        KoguardDictionary.from_sources(
            blacklist=invalid_entries,
            include_defaults=False,
        )


def test_dictionary_wraps_file_errors(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.txt"

    with pytest.raises(DictionaryError, match="failed to read blacklist"):
        KoguardDictionary.from_sources(
            blacklist_path=missing_path,
            include_defaults=False,
        )


def test_dictionary_wraps_encoding_errors(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.txt"
    invalid_path.write_bytes(b"\xff")

    with pytest.raises(DictionaryError, match="failed to read whitelist"):
        KoguardDictionary.from_sources(
            whitelist_path=invalid_path,
            include_defaults=False,
        )
