"""Tests for public Koguard exceptions."""

import pickle

from koguard import FuzzyOperationLimitError, InputTooLongError, KoguardError


def test_input_too_long_error_exposes_lengths() -> None:
    error = InputTooLongError(actual_length=10, max_length=5)

    assert isinstance(error, KoguardError)
    assert error.actual_length == 10
    assert error.max_length == 5
    assert str(error) == "input length 10 exceeds the configured limit of 5"


def test_input_too_long_error_supports_pickle_round_trip() -> None:
    error = InputTooLongError(actual_length=10, max_length=5)

    restored = pickle.loads(pickle.dumps(error))

    assert isinstance(restored, InputTooLongError)
    assert restored.actual_length == 10
    assert restored.max_length == 5
    assert str(restored) == str(error)


def test_fuzzy_operation_limit_error_exposes_limit_without_input() -> None:
    error = FuzzyOperationLimitError(max_operations=10)

    assert isinstance(error, KoguardError)
    assert error.max_operations == 10
    assert str(error) == "fuzzy matching exceeded the configured limit of 10 operations"


def test_fuzzy_operation_limit_error_supports_pickle_round_trip() -> None:
    error = FuzzyOperationLimitError(max_operations=10)

    restored = pickle.loads(pickle.dumps(error))

    assert isinstance(restored, FuzzyOperationLimitError)
    assert restored.max_operations == 10
    assert str(restored) == str(error)
