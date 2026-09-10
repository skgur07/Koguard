"""Public masking and narrowly scoped dictionary expansion regressions."""

from typing import cast

import pytest

from koguard import EngineConfig, InputTooLongError, KoguardDictionary, KoguardEngine
from koguard.exceptions import FuzzyOperationLimitError


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("Ａ\t정상  문장🙂", "Ａ\t정상  문장🙂"),
        ("앞 시발 뒤 병신!", "앞 ** 뒤 **!"),
        ("개새끼시발", "*****"),
        ("위기가 닥쳐올 것이다. 시발", "위기가 닥쳐올 것이다. **"),
        ("🙂시\u200b발\tＡ", "🙂***\tＡ"),
    ],
)
def test_mask_preserves_original_outside_detected_spans(text: str, expected: str) -> None:
    assert KoguardEngine().mask(text) == expected


@pytest.mark.parametrize("text", ["시 * 발", "시이이발", "ㅅㅣㅂㅏㄹ", "tlqkf"])
def test_mask_covers_entire_original_obfuscation(text: str) -> None:
    assert KoguardEngine(profile="aggressive").mask(text) == "*" * len(text)


def test_mask_custom_character_and_custom_whitelist() -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["금칙어"], whitelist=["금칙어사전"], include_defaults=False
    )
    engine = KoguardEngine(dictionary=dictionary)
    assert engine.mask("금칙어사전 금칙어", char="#") == "금칙어사전 ###"
    assert engine.mask("금칙어", char="🛑") == "🛑🛑🛑"


def test_mask_respects_transformed_whitelist() -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["tlqkf"], whitelist=["시발"], include_defaults=False
    )
    assert KoguardEngine(profile="aggressive", dictionary=dictionary).mask("tlqkf") == "tlqkf"


@pytest.mark.parametrize("char", ["", "**", "e\u0301"])
def test_mask_rejects_character_lengths_other_than_one(char: str) -> None:
    with pytest.raises(ValueError, match="one Unicode code point"):
        KoguardEngine().mask("정상", char=char)


def test_mask_rejects_non_string_character() -> None:
    with pytest.raises(TypeError, match="char must be a string"):
        KoguardEngine().mask("정상", char=cast(str, 1))


def test_mask_preserves_input_validation_and_work_limit() -> None:
    with pytest.raises(TypeError, match="text must be a string"):
        KoguardEngine().mask(cast(str, None))
    engine = KoguardEngine(config=EngineConfig(max_input_length=3))
    assert engine.mask("가나다") == "가나다"
    with pytest.raises(InputTooLongError):
        engine.mask("가나다라")
    with pytest.raises(FuzzyOperationLimitError):
        KoguardEngine(config=EngineConfig(fuzzy_max_operations=1)).mask("병신 abcdef")


def test_confirmed_variant_is_detected_and_masked() -> None:
    engine = KoguardEngine()
    assert engine.contains("븅신")
    result = engine.check("앞 븅신 뒤")
    assert [(m.start, m.end, m.term) for m in result.matches] == [(2, 4, "븅신")]
    assert engine.mask("앞 븅신 뒤") == "앞 ** 뒤"


@pytest.mark.parametrize("text", ["병원에 갑니다", "신발을 샀다", "뷰가 좋다", "빙수 먹자"])
def test_variant_expansion_keeps_diagnostic_negatives(text: str) -> None:
    assert not KoguardEngine().contains(text)
