"""Immutable blacklist, whitelist, and alias loading."""

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from koguard.config import NormalizationForm
from koguard.engine.normalizer import normalize_text
from koguard.exceptions import DictionaryError
from koguard.models import AliasMode, AliasRule

_DEFAULT_DATA_PACKAGE = "koguard.data"


def _read_packaged_lines(filename: str) -> tuple[str, ...]:
    try:
        content = files(_DEFAULT_DATA_PACKAGE).joinpath(filename).read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DictionaryError(f"failed to read packaged dictionary: {filename}") from exc
    return tuple(content.splitlines())


def _read_file_lines(path: str | Path, label: str) -> tuple[str, ...]:
    resolved_path = Path(path)
    try:
        content = resolved_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DictionaryError(f"failed to read {label} dictionary: {resolved_path}") from exc
    return tuple(content.splitlines())


def _normalize_entries(
    entries: Iterable[str],
    unicode_form: NormalizationForm,
    label: str,
) -> set[str]:
    normalized_entries: set[str] = set()
    for entry in entries:
        if not isinstance(entry, str):
            raise DictionaryError(f"{label} entries must be strings")

        stripped = entry.strip()
        if not stripped or stripped.startswith("#"):
            continue

        normalized = normalize_text(stripped, unicode_form).text.strip()
        if normalized:
            normalized_entries.add(normalized)
    return normalized_entries


def _normalize_alias_rules(
    rules: Iterable[AliasRule],
    unicode_form: NormalizationForm,
    label: str,
) -> tuple[AliasRule, ...]:
    normalized_by_alias: dict[str, AliasRule] = {}
    for rule in rules:
        if not isinstance(rule, AliasRule):
            raise DictionaryError(f"{label} alias entries must be AliasRule instances")

        normalized_alias = normalize_text(rule.alias.strip(), unicode_form).text.strip()
        normalized_term = normalize_text(rule.term.strip(), unicode_form).text.strip()
        if not normalized_alias or not normalized_term:
            raise DictionaryError(f"{label} alias and term must not be blank")

        normalized_rule = AliasRule(
            alias=normalized_alias,
            term=normalized_term,
            mode=rule.mode,
        )
        existing = normalized_by_alias.get(normalized_alias)
        if existing is not None and existing != normalized_rule:
            raise DictionaryError(f"{label} alias has conflicting rules: {rule.alias}")
        normalized_by_alias[normalized_alias] = normalized_rule

    return tuple(
        sorted(
            normalized_by_alias.values(),
            key=lambda rule: (-len(rule.alias), rule.alias, rule.mode.value, rule.term),
        )
    )


def _parse_alias_lines(
    entries: Iterable[str],
    unicode_form: NormalizationForm,
    label: str,
) -> tuple[AliasRule, ...]:
    rules: list[AliasRule] = []
    for line_number, entry in enumerate(entries, start=1):
        stripped = entry.strip()
        if not stripped or stripped.startswith("#"):
            continue

        fields = tuple(field.strip() for field in entry.split("\t"))
        if len(fields) != 3 or not all(fields):
            raise DictionaryError(
                f"invalid {label} alias entry at line {line_number}: "
                "expected 3 tab-separated fields"
            )
        alias, term, raw_mode = fields
        try:
            mode = AliasMode(raw_mode)
            rules.append(AliasRule(alias=alias, term=term, mode=mode))
        except (TypeError, ValueError) as exc:
            raise DictionaryError(f"invalid {label} alias entry at line {line_number}") from exc

    return _normalize_alias_rules(rules, unicode_form, label)


@dataclass(frozen=True, slots=True)
class KoguardDictionary:
    """Thread-safe, normalized dictionary indexes."""

    blacklist: frozenset[str]
    whitelist: frozenset[str]
    unicode_form: NormalizationForm
    aliases: tuple[AliasRule, ...] = ()

    def __post_init__(self) -> None:
        source_aliases = tuple(self.aliases)
        resolved_aliases = _normalize_alias_rules(
            source_aliases,
            self.unicode_form,
            "dictionary",
        )
        if len(resolved_aliases) != len(source_aliases):
            raise DictionaryError("aliases must not contain duplicate normalized forms")
        if any(rule.term not in self.blacklist for rule in resolved_aliases):
            raise DictionaryError("every alias canonical term must exist in the blacklist")
        object.__setattr__(self, "aliases", resolved_aliases)

    @classmethod
    def default(
        cls,
        unicode_form: NormalizationForm = "NFKC",
    ) -> "KoguardDictionary":
        """Load the dictionaries bundled with Koguard."""

        return cls.from_sources(unicode_form=unicode_form)

    @classmethod
    def from_sources(
        cls,
        *,
        blacklist: Iterable[str] = (),
        whitelist: Iterable[str] = (),
        blacklist_path: str | Path | None = None,
        whitelist_path: str | Path | None = None,
        aliases: Iterable[AliasRule] = (),
        alias_path: str | Path | None = None,
        include_defaults: bool = True,
        unicode_form: NormalizationForm = "NFKC",
    ) -> "KoguardDictionary":
        """Build indexes from packaged data, iterables, and optional UTF-8 files."""

        blacklist_entries: set[str] = set()
        whitelist_entries: set[str] = set()
        alias_rules: list[AliasRule] = []

        if include_defaults:
            blacklist_entries.update(
                _normalize_entries(
                    _read_packaged_lines("badwords.txt"),
                    unicode_form,
                    "blacklist",
                )
            )
            whitelist_entries.update(
                _normalize_entries(
                    _read_packaged_lines("whitelist.txt"),
                    unicode_form,
                    "whitelist",
                )
            )
            default_aliases = _parse_alias_lines(
                _read_packaged_lines("aliases.tsv"),
                unicode_form,
                "packaged",
            )
            alias_rules.extend(default_aliases)
            blacklist_entries.update(rule.term for rule in default_aliases)

        blacklist_entries.update(_normalize_entries(blacklist, unicode_form, "blacklist"))
        whitelist_entries.update(_normalize_entries(whitelist, unicode_form, "whitelist"))

        if blacklist_path is not None:
            blacklist_entries.update(
                _normalize_entries(
                    _read_file_lines(blacklist_path, "blacklist"),
                    unicode_form,
                    "blacklist",
                )
            )
        if whitelist_path is not None:
            whitelist_entries.update(
                _normalize_entries(
                    _read_file_lines(whitelist_path, "whitelist"),
                    unicode_form,
                    "whitelist",
                )
            )

        alias_rules.extend(_normalize_alias_rules(aliases, unicode_form, "custom"))
        if alias_path is not None:
            alias_rules.extend(
                _parse_alias_lines(
                    _read_file_lines(alias_path, "alias"),
                    unicode_form,
                    "custom",
                )
            )
        resolved_aliases = _normalize_alias_rules(alias_rules, unicode_form, "combined")
        if any(rule.term not in blacklist_entries for rule in resolved_aliases):
            raise DictionaryError("every alias canonical term must exist in the blacklist")

        return cls(
            blacklist=frozenset(blacklist_entries),
            whitelist=frozenset(whitelist_entries),
            unicode_form=unicode_form,
            aliases=resolved_aliases,
        )

    @property
    def ordered_blacklist(self) -> tuple[str, ...]:
        """Blacklist terms ordered deterministically, longest first."""

        return tuple(sorted(self.blacklist, key=lambda term: (-len(term), term)))

    @property
    def ordered_whitelist(self) -> tuple[str, ...]:
        """Whitelist terms ordered deterministically, longest first."""

        return tuple(sorted(self.whitelist, key=lambda term: (-len(term), term)))

    @property
    def ordered_aliases(self) -> tuple[AliasRule, ...]:
        """Alias rules ordered deterministically, longest form first."""

        return self.aliases
