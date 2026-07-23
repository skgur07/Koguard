"""Tests for public Koguard exceptions."""

from koguard import InputTooLongError, KoguardError


def test_input_too_long_error_exposes_lengths() -> None:
    error = InputTooLongError(actual_length=10, max_length=5)

    assert isinstance(error, KoguardError)
    assert error.actual_length == 10
    assert error.max_length == 5
    assert str(error) == "input length 10 exceeds the configured limit of 5"
