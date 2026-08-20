"""Tests for immutable dictionary loading."""

from pathlib import Path
from typing import cast

import pytest

from koguard import (
    AliasMode,
    AliasRule,
    DictionaryError,
    KoguardDictionary,
    KoguardEngine,
    NormalizationForm,
)


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
        "개자식",
        "뒤져",
        "느그애미",
        "빡대가리",
        "틀딱",
        "따먹다",
        "보지",
        "조센징",
        "sibal",
        "ssibal",
        "shibal",
        "새끼",
        "병신새끼",
    } <= dictionary.blacklist
    assert len(dictionary.blacklist) >= 50
    assert "병신년" not in dictionary.whitelist
    assert "시발점" not in dictionary.whitelist


@pytest.mark.parametrize(
    "term",
    [
        "틀딱",
        "따먹다",
        "보지",
        "조센징",
        "sibal",
        "ssibal",
        "shibal",
        "새끼",
        "병신새끼",
    ],
)
def test_default_dictionary_detects_owner_approved_literal_expansion(term: str) -> None:
    dictionary = KoguardDictionary.default()

    assert term in dictionary.blacklist


def test_packaged_korcen_terms_include_pinned_mit_notice() -> None:
    data_directory = Path("src/koguard/data")
    notice = (data_directory / "NOTICE.md").read_text(encoding="utf-8")
    license_text = (data_directory / "KORCEN-MIT.txt").read_text(encoding="utf-8")

    assert "https://github.com/Tanat05/korcen" in notice
    assert "eecd9763dbdccce3dc96ddb578ef0b6396058fa9" in notice
    assert "MIT License" in license_text
    assert "Copyright (c) 2026 Tanat" in license_text


def test_promoted_curse_data_terms_include_pinned_mit_notice() -> None:
    data_directory = Path("src/koguard/data")
    notice = (data_directory / "NOTICE.md").read_text(encoding="utf-8")
    license_text = (data_directory / "CURSE-DETECTION-DATA-MIT.txt").read_text(encoding="utf-8")

    assert "https://github.com/2runo/Curse-detection-data" in notice
    assert "ff241621e103b6f220d30de324d0d07987887308" in notice
    assert "MIT License" in license_text
    assert "Copyright (c) 2020 2runo" in license_text


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


def test_dictionary_loads_normalized_alias_rules_from_utf8_file(tmp_path: Path) -> None:
    alias_path = tmp_path / "aliases.tsv"
    alias_path.write_text(
        "# alias\tterm\tmode\nㅄ\t병신\texact_token\nㅈ같\t좆같다\ttoken_prefix\n",
        encoding="utf-8",
    )

    dictionary = KoguardDictionary.from_sources(
        blacklist=["병신", "좆같다"],
        alias_path=alias_path,
        include_defaults=False,
    )

    assert dictionary.ordered_aliases == (
        AliasRule(alias="ᄌ같", term="좆같다", mode=AliasMode.TOKEN_PREFIX),
        AliasRule(alias="ᄡ", term="병신", mode=AliasMode.EXACT_TOKEN),
    )


def test_dictionary_normalizes_aliases_passed_to_direct_constructor() -> None:
    dictionary = KoguardDictionary(
        blacklist=frozenset({"병신"}),
        whitelist=frozenset(),
        unicode_form="NFKC",
        aliases=(AliasRule("ㅄ", "병신", AliasMode.EXACT_TOKEN),),
    )

    assert dictionary.aliases == (AliasRule("ᄡ", "병신", AliasMode.EXACT_TOKEN),)


def test_direct_dictionary_copies_and_normalizes_mutable_collections() -> None:
    blacklist = {" 욕설 ", "ＳＩＢＡＬ"}
    whitelist = {" 정상 표현 "}
    dictionary = KoguardDictionary(
        blacklist=cast(frozenset[str], blacklist),
        whitelist=cast(frozenset[str], whitelist),
        unicode_form="NFKC",
    )
    engine = KoguardEngine(dictionary=dictionary)

    blacklist.add("추가")
    whitelist.add("추가 보호")

    assert type(dictionary.blacklist) is frozenset
    assert type(dictionary.whitelist) is frozenset
    assert dictionary.blacklist == frozenset({"욕설", "SIBAL"})
    assert dictionary.whitelist == frozenset({"정상 표현"})
    assert "추가" not in engine.dictionary.blacklist
    assert engine.contains("추가") is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("blacklist", ["정상", 123]),
        ("whitelist", [object()]),
        ("unicode_form", "NFD"),
    ],
)
def test_direct_dictionary_rejects_invalid_runtime_values(field: str, value: object) -> None:
    values: dict[str, object] = {
        "blacklist": frozenset({"욕설"}),
        "whitelist": frozenset(),
        "unicode_form": "NFKC",
    }
    values[field] = value

    with pytest.raises(DictionaryError, match=field):
        KoguardDictionary(
            blacklist=cast(frozenset[str], values["blacklist"]),
            whitelist=cast(frozenset[str], values["whitelist"]),
            unicode_form=cast(NormalizationForm, values["unicode_form"]),
        )


@pytest.mark.parametrize(
    "line",
    [
        "ㅄ\t병신",
        "ㅄ\t병신\tunknown",
        "ㅄ\t병신\texact_token\textra",
    ],
)
def test_dictionary_rejects_malformed_alias_files(tmp_path: Path, line: str) -> None:
    alias_path = tmp_path / "aliases.tsv"
    alias_path.write_text(f"{line}\n", encoding="utf-8")

    with pytest.raises(DictionaryError, match="alias"):
        KoguardDictionary.from_sources(
            blacklist=["병신"],
            alias_path=alias_path,
            include_defaults=False,
        )


def test_dictionary_rejects_alias_without_blacklisted_canonical_term() -> None:
    with pytest.raises(DictionaryError, match="blacklist"):
        KoguardDictionary.from_sources(
            aliases=[AliasRule("ㅄ", "병신", AliasMode.EXACT_TOKEN)],
            include_defaults=False,
        )


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
