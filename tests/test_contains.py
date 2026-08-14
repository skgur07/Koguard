"""Public contract tests for the boolean detection convenience API."""

from concurrent.futures import ThreadPoolExecutor
from typing import cast
from unittest.mock import patch

import pytest

from koguard import (
    EngineConfig,
    InputTooLongError,
    KoguardDictionary,
    KoguardEngine,
    ProfileName,
)
from koguard.models import CheckResult


@pytest.mark.parametrize(
    ("profile", "text"),
    [
        ("strict", "정상 문장입니다"),
        ("strict", "시발점"),
        ("balanced", "ㅅㅂ"),
        ("aggressive", "tlqkf"),
    ],
)
def test_contains_matches_check_detected_for_every_profile(
    profile: ProfileName,
    text: str,
) -> None:
    engine = KoguardEngine(profile=profile)

    result = engine.contains(text)

    assert type(result) is bool
    assert result is engine.check(text).detected


@pytest.mark.parametrize(
    "config",
    [
        EngineConfig(),
        EngineConfig(exact_matching=False),
        EngineConfig(max_input_length=32),
    ],
)
def test_contains_matches_check_detected_for_direct_config(config: EngineConfig) -> None:
    engine = KoguardEngine(config=config)

    assert engine.contains("시발점") is engine.check("시발점").detected


def test_contains_uses_custom_dictionary_and_whitelist_policy() -> None:
    dictionary = KoguardDictionary.from_sources(
        blacklist=["금칙어"],
        whitelist=["금칙어가 포함된 정상 표현"],
        include_defaults=False,
    )
    engine = KoguardEngine(dictionary=dictionary)

    assert engine.contains("앞 금칙어 뒤") is True
    assert engine.contains("금칙어가 포함된 정상 표현") is False


def test_contains_delegates_to_check_once() -> None:
    engine = KoguardEngine()
    expected = CheckResult(normalized_text="검사할 문장")

    with patch.object(KoguardEngine, "check", return_value=expected) as check:
        result = engine.contains("검사할 문장")

    assert result is False
    check.assert_called_once_with("검사할 문장")


def test_contains_preserves_non_string_validation() -> None:
    engine = KoguardEngine()
    invalid_text = cast(str, 123)

    with pytest.raises(TypeError) as check_error:
        engine.check(invalid_text)
    with pytest.raises(TypeError) as contains_error:
        engine.contains(invalid_text)

    assert str(contains_error.value) == str(check_error.value)


def test_contains_preserves_input_length_limit() -> None:
    engine = KoguardEngine(config=EngineConfig(max_input_length=3))

    with pytest.raises(InputTooLongError) as check_error:
        engine.check("1234")
    with pytest.raises(InputTooLongError) as contains_error:
        engine.contains("1234")

    assert contains_error.value.actual_length == check_error.value.actual_length == 4
    assert contains_error.value.max_length == check_error.value.max_length == 3
    assert str(contains_error.value) == str(check_error.value)


def test_contains_is_safe_for_concurrent_calls() -> None:
    engine = KoguardEngine()
    texts = ["정상 문장", "시발점", "병신", "ㅅㅂ"] * 10

    with ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(engine.contains, texts))

    assert results == [False, True, True, True] * 10
