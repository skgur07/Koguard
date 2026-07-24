"""Tests for public Koguard exceptions."""

import pickle

from koguard import InputTooLongError, KoguardError


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
