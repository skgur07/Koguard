"""Unit tests for low-cost exact matching."""

import pytest

from koguard import KoguardDictionary
from koguard.engine.matcher import ExactMatcher, _MappedCandidate
from koguard.engine.normalizer import normalize_text


def make_matcher(
    *,
    blacklist: list[str],
    whitelist: list[str] | None = None,
) -> ExactMatcher:
    dictionary = KoguardDictionary.from_sources(
        blacklist=blacklist,
        whitelist=whitelist or [],
        include_defaults=False,
    )
    return ExactMatcher(dictionary)


def test_exact_matcher_prefers_longest_shared_prefix_and_keeps_later_match() -> None:
    matcher = make_matcher(blacklist=["금", "금칙", "욕설"])
    text = "금칙 그리고 욕설"

    matches = matcher.find(text, normalize_text(text, "NFKC"))

    assert [match.term for match in matches] == ["금칙", "욕설"]
    assert [match.matched_text for match in matches] == ["금칙", "욕설"]


def test_exact_matcher_applies_whitelist_to_only_overlapping_span() -> None:
    matcher = make_matcher(
        blacklist=["시발", "병신"],
        whitelist=["시발점"],
    )
    text = "시발점과 병신"

    matches = matcher.find(text, normalize_text(text, "NFKC"))

    assert [match.term for match in matches] == ["병신"]


def test_exact_matcher_does_not_compare_candidates_pairwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_pairwise_overlap(
        self: _MappedCandidate,
        other: _MappedCandidate,
    ) -> bool:
        raise AssertionError("candidate overlap must use position masks")

    monkeypatch.setattr(_MappedCandidate, "overlaps", reject_pairwise_overlap)
    matcher = make_matcher(
        blacklist=["a" * size for size in range(1, 9)],
        whitelist=["정상"],
    )

    matches = matcher.find("a" * 64, normalize_text("a" * 64, "NFKC"))

    assert len(matches) == 8
    assert all(match.term == "a" * 8 for match in matches)
