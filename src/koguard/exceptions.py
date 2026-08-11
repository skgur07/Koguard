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
        super().__init__(actual_length, max_length)

    def __str__(self) -> str:
        return (
            f"input length {self.actual_length} exceeds the configured limit of {self.max_length}"
        )


class FuzzyOperationLimitError(KoguardError, RuntimeError):
    """Raised when one fuzzy check would exceed its deterministic work budget."""

    def __init__(self, max_operations: int) -> None:
        self.max_operations = max_operations
        super().__init__(max_operations)

    def __str__(self) -> str:
        return f"fuzzy matching exceeded the configured limit of {self.max_operations} operations"
