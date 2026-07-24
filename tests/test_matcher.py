"""Unit tests for Trie-based exact matching."""

from koguard import KoguardDictionary
from koguard.engine.matcher import TrieMatcher
from koguard.engine.normalizer import normalize_text


def make_matcher(
    *,
    blacklist: list[str],
    whitelist: list[str] | None = None,
) -> TrieMatcher:
    dictionary = KoguardDictionary.from_sources(
        blacklist=blacklist,
        whitelist=whitelist or [],
        include_defaults=False,
    )
    return TrieMatcher(dictionary)


def test_trie_matcher_prefers_longest_shared_prefix_and_keeps_later_match() -> None:
    matcher = make_matcher(blacklist=["금", "금칙", "욕설"])
    text = "금칙 그리고 욕설"

    matches = matcher.find(text, normalize_text(text, "NFKC"))

    assert [match.term for match in matches] == ["금칙", "욕설"]
    assert [match.matched_text for match in matches] == ["금칙", "욕설"]


def test_trie_matcher_applies_whitelist_to_only_overlapping_span() -> None:
    matcher = make_matcher(
        blacklist=["시발", "병신"],
        whitelist=["시발점"],
    )
    text = "시발점과 병신"

    matches = matcher.find(text, normalize_text(text, "NFKC"))

    assert [match.term for match in matches] == ["병신"]
