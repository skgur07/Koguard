"""Public exceptions raised by Koguard."""


class KoguardError(Exception):
    """Base class for all Koguard-specific errors."""


class ConfigurationError(KoguardError, ValueError):
    """Raised when engine configuration is invalid."""


class DictionaryError(KoguardError):
    """Raised when dictionary data cannot be loaded or validated."""


class InputTooLongError(KoguardError, ValueError):
    """Raised when input exceeds the configured length limit."""

    def __init__(self, actual_length: int, max_length: int) -> None:
        self.actual_length = actual_length
        self.max_length = max_length
        super().__init__(
            f"input length {actual_length} exceeds the configured limit of {max_length}"
        )
