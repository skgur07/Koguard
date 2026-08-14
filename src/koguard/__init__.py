"""Koguard public package API."""

from importlib.metadata import PackageNotFoundError, version

from koguard.config import EngineConfig, NormalizationForm, ProfileName
from koguard.engine import KoguardDictionary, KoguardEngine
from koguard.exceptions import (
    ConfigurationError,
    DictionaryError,
    FuzzyOperationLimitError,
    InputTooLongError,
    KoguardError,
)
from koguard.models import AliasMode, AliasRule, CheckResult, Match, MatchMethod

try:
    __version__ = version("koguard")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0.0.0"

__all__ = [
    "CheckResult",
    "AliasMode",
    "AliasRule",
    "ConfigurationError",
    "DictionaryError",
    "EngineConfig",
    "FuzzyOperationLimitError",
    "InputTooLongError",
    "KoguardDictionary",
    "KoguardEngine",
    "KoguardError",
    "Match",
    "MatchMethod",
    "NormalizationForm",
    "ProfileName",
    "__version__",
]
