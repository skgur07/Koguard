"""Closed public API surface tests for the 0.1.0 core package."""

import tomllib
from pathlib import Path

import koguard
from koguard import KoguardDictionary, KoguardEngine, MatchMethod

_EXPECTED_EXPORTS = {
    "AliasMode",
    "AliasRule",
    "CheckResult",
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
}
_EXPECTED_MATCH_METHODS = {
    "exact",
    "repeated",
    "separator",
    "whitespace",
    "mixed",
    "choseong",
    "alias",
    "keyboard",
    "jamo",
    "levenshtein",
    "none",
}


def _public_class_names(class_: type[object]) -> set[str]:
    return {name for name in class_.__dict__ if not name.startswith("_")}


def test_top_level_exports_are_a_closed_documented_set() -> None:
    inventory = Path("docs/public-api-inventory.md").read_text(encoding="utf-8")

    assert set(koguard.__all__) == _EXPECTED_EXPORTS
    for name in _EXPECTED_EXPORTS:
        assert getattr(koguard, name) is not None
        assert f"`{name}`" in inventory


def test_engine_and_dictionary_expose_only_implemented_core_operations() -> None:
    assert _public_class_names(KoguardEngine) == {
        "check",
        "config",
        "contains",
        "dictionary",
    }
    assert _public_class_names(KoguardDictionary) == {
        "aliases",
        "blacklist",
        "default",
        "from_sources",
        "ordered_aliases",
        "ordered_blacklist",
        "ordered_whitelist",
        "unicode_form",
        "whitelist",
    }


def test_match_method_contains_only_runtime_and_clean_result_values() -> None:
    assert {method.value for method in MatchMethod} == _EXPECTED_MATCH_METHODS


def test_future_extension_symbols_are_not_public() -> None:
    for name in (
        "Adapter",
        "AsyncPlugin",
        "BasePlugin",
        "EmbeddingPlugin",
        "PluginManager",
        "acheck",
        "mask",
    ):
        assert not hasattr(koguard, name)

    assert not hasattr(koguard, "check")
    assert not hasattr(koguard, "contains")


def test_core_package_has_no_future_extension_runtime_or_dependencies() -> None:
    package_root = Path("src/koguard")
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert not (package_root / "adapters").exists()
    assert not (package_root / "plugins").exists()
    assert not (package_root / "ai").exists()
    assert project["dependencies"] == []
    assert "optional-dependencies" not in project
