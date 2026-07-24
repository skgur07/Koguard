"""Immutable blacklist and whitelist loading."""

from collections.abc import Iterable
from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path

from koguard.config import NormalizationForm
from koguard.engine.normalizer import normalize_text
from koguard.exceptions import DictionaryError

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


@dataclass(frozen=True, slots=True)
class KoguardDictionary:
    """Thread-safe, normalized dictionary indexes."""

    blacklist: frozenset[str]
    whitelist: frozenset[str]
    unicode_form: NormalizationForm

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
        include_defaults: bool = True,
        unicode_form: NormalizationForm = "NFKC",
    ) -> "KoguardDictionary":
        """Build indexes from packaged data, iterables, and optional UTF-8 files."""

        blacklist_entries: set[str] = set()
        whitelist_entries: set[str] = set()

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

        return cls(
            blacklist=frozenset(blacklist_entries),
            whitelist=frozenset(whitelist_entries),
            unicode_form=unicode_form,
        )

    @property
    def ordered_blacklist(self) -> tuple[str, ...]:
        """Blacklist terms ordered deterministically, longest first."""

        return tuple(sorted(self.blacklist, key=lambda term: (-len(term), term)))

    @property
    def ordered_whitelist(self) -> tuple[str, ...]:
        """Whitelist terms ordered deterministically, longest first."""

        return tuple(sorted(self.whitelist, key=lambda term: (-len(term), term)))
