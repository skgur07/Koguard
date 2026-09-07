"""Accuracy budgets enforced against the independent evaluation corpus.

`tests/corpus/*` proves that specific behaviours do not regress. It cannot see a
precision collapse, because it holds almost no ordinary sentences. These budgets
close that gap: they fail when a dictionary or matcher change starts flagging
normal Korean.

Budgets are absolute counts, not rates. `docs/product-focus-plan.md` section 8.3
asks for a 0.5% clean false-positive rate, which at the current corpus size is
0.6 sentences -- a threshold no measurement can land on. The rate becomes the
right unit once the corpus reaches the section 6.7 target.
"""

from evaluation.koguard_runner import measure
from evaluation.loader import load_all_cases

#: Hard-negative sentences the default engine may still flag.
#: Measured 2026-09-04: 2 of 122.
#:   hn-kkeojyeo-03  촛불이 바람에 꺼져 어두워졌다  -- auxiliary verb not on the whitelist
#:   hn-dwijil-01    온 집을 뒤질 각오로 찾았다      -- adnominal 뒤질 takes an open set of nouns
#: Neither more whitelist entries nor a per-term matching mode can fix these:
#: the term is the whole word here, so morphology carries no signal. They go
#: away only by moving the term out of the default dictionary.
MAX_CLEAN_FALSE_POSITIVE_CASES = 3

#: Occurrence recall the default engine must keep.
#: Measured 2026-09-04: 0.9286.
MIN_OCCURRENCE_RECALL = 0.90

#: Share of detections on real profanity that carry the gold canonical term.
#: Measured 2026-09-04: 0.9512 (2 mismatches, both `개새` shadowing `개새끼`).
#: These still block the sentence, so they are tracked apart from clean-sentence
#: false alarms rather than folded into the precision budget.
MIN_CANONICAL_TERM_AGREEMENT = 0.90


def test_default_engine_stays_within_the_clean_false_positive_budget() -> None:
    report = measure(load_all_cases())

    assert report.clean_cases >= 100, "budget is meaningless without enough clean sentences"
    assert report.clean_cases_with_a_detection <= MAX_CLEAN_FALSE_POSITIVE_CASES, (
        f"{report.clean_cases_with_a_detection} clean sentences were flagged: "
        f"{report.false_positive_case_ids}"
    )


def test_default_engine_keeps_its_recall_while_precision_improves() -> None:
    report = measure(load_all_cases())

    assert report.recall >= MIN_OCCURRENCE_RECALL, (
        f"recall dropped to {report.recall:.4f}; missed {report.false_negative_case_ids}"
    )


def test_default_engine_does_not_fuzzy_match_ordinary_words() -> None:
    """`미친` and `돌아` are ordinary Korean one edit away from dictionary terms."""

    report = measure(load_all_cases())
    flagged = set(report.false_positive_case_ids)

    assert "hn-michin-01" not in flagged
    assert "hn-michin-02" not in flagged
    assert "hn-dorai-01" not in flagged


def test_default_whitelist_protects_ordinary_verb_usage() -> None:
    """The bundled whitelist must cover the auxiliary-verb readings."""

    report = measure(load_all_cases())
    flagged = set(report.false_positive_case_ids)

    for case_id in ("hn-kkeojyeo-01", "hn-dakchyeo-01", "hn-dwijyeo-01", "hn-deungsin-01"):
        assert case_id not in flagged, f"{case_id} should be protected by the default whitelist"


def test_default_engine_labels_its_detections_with_the_gold_canonical_term() -> None:
    report = measure(load_all_cases())

    assert report.canonical_term_agreement >= MIN_CANONICAL_TERM_AGREEMENT, (
        f"{report.term_mismatches} detections landed on real profanity "
        f"under the wrong canonical term"
    )
