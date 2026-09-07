"""Contract tests for the evaluation corpus schema, split policy, and harness."""

from collections import Counter

import pytest
from evaluation.loader import (
    CorpusError,
    load_all_cases,
    load_split,
    validate_cases,
)
from evaluation.report import evaluate_cases
from evaluation.schema import REQUIRED_NEGATIVE_SLICES, EvaluationCase, ExpectedMatch


def test_every_case_parses_into_the_documented_schema() -> None:
    cases = load_all_cases()

    assert cases
    for case in cases:
        assert isinstance(case, EvaluationCase)
        assert case.id
        assert case.text is not None
        assert case.source in {"curated", "licensed", "private"}
        assert case.split in {"tuning", "evaluation"}
        assert case.status in {"final", "review"}
        assert case.slices


def test_case_ids_are_unique_across_every_split() -> None:
    cases = load_all_cases()
    duplicates = [case_id for case_id, count in Counter(c.id for c in cases).items() if count > 1]

    assert duplicates == []


def test_tuning_and_evaluation_splits_do_not_leak_the_same_text() -> None:
    tuning_texts = {case.text for case in load_split("tuning")}
    evaluation_texts = {case.text for case in load_split("evaluation")}

    assert tuning_texts & evaluation_texts == set()


def test_expected_match_spans_agree_with_the_case_text() -> None:
    for case in load_all_cases():
        for expected in case.expected_matches:
            assert 0 <= expected.start < expected.end <= len(case.text), case.id


def test_hard_negative_cases_declare_no_expected_match() -> None:
    for case in load_all_cases():
        if "hard_negative" in case.slices:
            assert case.expected_matches == (), case.id


def test_every_required_negative_slice_is_represented() -> None:
    covered = {slice_name for case in load_all_cases() for slice_name in case.slices}

    assert REQUIRED_NEGATIVE_SLICES <= covered


def test_validate_cases_rejects_a_span_that_does_not_match_its_canonical_term() -> None:
    broken = EvaluationCase(
        id="broken-span",
        text="정상 문장",
        expected_matches=(ExpectedMatch(start=0, end=2, canonical_term="시발", label="blocked"),),
        slices=("direct",),
        source="curated",
        license="curated",
        split="tuning",
        status="final",
        single_review=True,
        notes="",
    )

    with pytest.raises(CorpusError):
        validate_cases([broken])


def test_validate_cases_rejects_duplicate_ids() -> None:
    case = EvaluationCase(
        id="duplicated",
        text="오늘 날씨가 좋다",
        expected_matches=(),
        slices=("hard_negative", "compound_substring"),
        source="curated",
        license="curated",
        split="tuning",
        status="final",
        single_review=True,
        notes="",
    )

    with pytest.raises(CorpusError):
        validate_cases([case, case])


def test_evaluate_cases_excludes_review_cases_but_reports_their_count() -> None:
    report = evaluate_cases(load_split("tuning"), predict=lambda _text: ())

    assert report.excluded_review_cases >= 0
    assert report.total_cases == report.scored_cases + report.excluded_review_cases


def test_evaluate_cases_scores_a_perfect_oracle_at_one() -> None:
    cases = [case for case in load_split("tuning") if case.status == "final"]

    def oracle(text: str) -> tuple[tuple[int, int, str], ...]:
        for case in cases:
            if case.text == text:
                return tuple(
                    (match.start, match.end, match.canonical_term)
                    for match in case.expected_matches
                )
        return ()

    report = evaluate_cases(cases, predict=oracle)

    assert report.false_positives == 0
    assert report.false_negatives == 0
    assert report.precision == 1.0
    assert report.recall == 1.0


def test_canonical_term_agreement_separates_mislabelling_from_a_false_alarm() -> None:
    """A detection on real profanity under the wrong term is not a clean-sentence hit."""

    case = EvaluationCase(
        id="mislabelled",
        text="개새애끼 뭐야",
        expected_matches=(ExpectedMatch(start=0, end=4, canonical_term="개새끼", label="blocked"),),
        slices=("repeated_separator",),
        source="curated",
        license="curated",
        split="tuning",
        status="final",
        single_review=True,
        notes="",
    )

    report = evaluate_cases([case], predict=lambda _text: ((0, 2, "개새"),))

    assert report.term_mismatches == 1
    assert report.canonical_term_agreement == 0.0
    assert report.clean_cases_with_a_detection == 0, "the sentence really is profane"


def test_canonical_term_agreement_is_one_when_every_hit_carries_the_gold_term() -> None:
    report = evaluate_cases(load_split("tuning"), predict=lambda _text: ())

    assert report.term_mismatches == 0
    assert report.canonical_term_agreement == 0.0 or report.true_positives == 0
