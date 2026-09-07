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

from koguard import EngineConfig

#: Hard-negative sentences the default engine may still flag.
#: Measured 2026-09-07: 0 of 122. The two that survived the whitelist work
#: (`꺼져`, `뒤질`) moved to the contextual tier, which was the only remaining
#: option: there the dictionary term is the whole word, so morphology carries no
#: signal to separate the ordinary reading.
#: The budget is zero rather than a cushion. A change that flags one clean
#: sentence should require the decision record plan section 12 asks for instead
#: of slipping in under slack left here.
MAX_CLEAN_FALSE_POSITIVE_CASES = 0

#: Occurrence recall the default engine must keep.
#: Measured 2026-09-07: 0.9048, down from 0.9286. The case given up is
#: `pos-direct-07` (`그만 꺼져 봐`): a real insult the default loses together
#: with the false positives that term caused. Services that need it opt into the
#: contextual tier.
MIN_OCCURRENCE_RECALL = 0.90

#: Share of detections on real profanity that carry the gold canonical term.
#: Measured 2026-09-07: 0.9500 (2 mismatches, both `개새` shadowing `개새끼`).
#: These still block the sentence, so they are tracked apart from clean-sentence
#: false alarms rather than folded into the precision budget.
MIN_CANONICAL_TERM_AGREEMENT = 0.90

#: What opting into the widest configuration costs, so the price stays visible
#: and cannot quietly grow. Measured 2026-09-07 with `aggressive` plus the
#: contextual tier: 5 of 122 clean sentences, three from fuzzy matching and two
#: from the contextual terms.
MAX_OPT_IN_CLEAN_FALSE_POSITIVE_CASES = 5


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
    """The bundled whitelist must cover the auxiliary-verb readings.

    `hn-kkeojyeo-01` is checked with the contextual tier instead: its term is no
    longer in the default dictionary, so it would pass here for the wrong reason.
    """

    report = measure(load_all_cases())
    flagged = set(report.false_positive_case_ids)

    for case_id in ("hn-dakchyeo-01", "hn-dwijyeo-01", "hn-deungsin-01"):
        assert case_id not in flagged, f"{case_id} should be protected by the default whitelist"


def test_contextual_tier_keeps_the_whitelist_protections() -> None:
    """Opting in widens the dictionary. It must not discard layer-2 coverage.

    Once `꺼져` and `뒤질` left the default dictionary, the default passes these
    cases for free. The assertion only means something with the tier switched
    back on, which is where it lives now.
    """

    report = measure(
        load_all_cases(),
        config=EngineConfig.aggressive(),
        include_contextual=True,
    )
    flagged = set(report.false_positive_case_ids)

    for case_id in ("hn-kkeojyeo-01", "hn-dakchyeo-01", "hn-dwijyeo-01", "hn-deungsin-01"):
        assert case_id not in flagged, f"{case_id} should be protected by the default whitelist"


def test_opting_into_the_widest_configuration_has_a_bounded_cost() -> None:
    report = measure(
        load_all_cases(),
        config=EngineConfig.aggressive(),
        include_contextual=True,
    )

    assert report.clean_cases_with_a_detection <= MAX_OPT_IN_CLEAN_FALSE_POSITIVE_CASES, (
        f"{report.clean_cases_with_a_detection} clean sentences were flagged: "
        f"{report.false_positive_case_ids}"
    )


def test_default_engine_labels_its_detections_with_the_gold_canonical_term() -> None:
    report = measure(load_all_cases())

    assert report.canonical_term_agreement >= MIN_CANONICAL_TERM_AGREEMENT, (
        f"{report.term_mismatches} detections landed on real profanity "
        f"under the wrong canonical term"
    )
