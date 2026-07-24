"""Koguard public package API."""

from importlib.metadata import PackageNotFoundError, version

from koguard.config import EngineConfig, NormalizationForm
from koguard.engine import KoguardDictionary, KoguardEngine
from koguard.exceptions import (
    ConfigurationError,
    DictionaryError,
    InputTooLongError,
    KoguardError,
)
from koguard.models import CheckResult, Match, MatchMethod

try:
    __version__ = version("koguard")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "CheckResult",
    "ConfigurationError",
    "DictionaryError",
    "EngineConfig",
    "InputTooLongError",
    "KoguardDictionary",
    "KoguardEngine",
    "KoguardError",
    "Match",
    "MatchMethod",
    "NormalizationForm",
    "__version__",
]
