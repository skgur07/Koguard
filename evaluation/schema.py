"""Annotation schema for the Koguard evaluation corpus.

The schema follows `docs/product-focus-plan.md` section 6.3. Cases live outside
the distributed package because they exist to judge release quality, not to be
shipped to library users.
"""

from dataclasses import dataclass
from typing import Literal

Source = Literal["curated", "licensed", "private"]
Split = Literal["tuning", "evaluation"]
Status = Literal["final", "review"]
Label = Literal["blocked", "allowed"]

#: Slices that describe how an expression is written or where it appears.
#: Section 6.2 of the product focus plan requires every one of these to exist
#: before a corpus can be used for a release judgement.
REQUIRED_NEGATIVE_SLICES: frozenset[str] = frozenset(
    {
        "hard_negative",
        "compound_substring",
        "suffix_boundary",
        "proper_noun_domain",
        "quotation_context",
        "unicode_edge",
        "input_limits",
    }
)

#: Slices that describe positive detections.
POSITIVE_SLICES: frozenset[str] = frozenset(
    {
        "direct",
        "spelling_variant",
        "choseong_alias",
        "jamo_keyboard",
        "repeated_separator",
        "whitespace_mixed",
        "fuzzy",
        "multiple_match",
    }
)

#: Slices where the written surface is deliberately not the canonical term,
#: so a span cannot be expected to spell that term out (``tlqkf`` for
#: ``시발``, ``시이이발`` for ``시발``).
OBFUSCATION_SLICES: frozenset[str] = frozenset(
    {
        "spelling_variant",
        "choseong_alias",
        "jamo_keyboard",
        "repeated_separator",
        "whitespace_mixed",
        "fuzzy",
    }
)

KNOWN_SLICES: frozenset[str] = REQUIRED_NEGATIVE_SLICES | POSITIVE_SLICES


@dataclass(frozen=True, slots=True)
class ExpectedMatch:
    """One gold-annotated detection span inside a case."""

    start: int
    end: int
    canonical_term: str
    label: Label


@dataclass(frozen=True, slots=True)
class EvaluationCase:
    """One annotated sentence.

    ``status`` separates settled judgements from cases a reviewer flagged as
    genuinely ambiguous. Ambiguous cases stay in the corpus so the count is
    visible, but automated scoring skips them.

    ``single_review`` records that only one person judged the case, so a reader
    can discount the result instead of assuming double annotation.
    """

    id: str
    text: str
    expected_matches: tuple[ExpectedMatch, ...]
    slices: tuple[str, ...]
    source: Source
    license: str
    split: Split
    status: Status
    single_review: bool
    notes: str
