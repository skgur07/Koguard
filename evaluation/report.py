"""Slice-aware scoring for the evaluation corpus.

Reports the metrics `docs/product-focus-plan.md` section 6.6 requires: occurrence
and sentence level precision/recall/F1, the clean-sentence false-positive rate,
per-slice counts, and span/term agreement.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from evaluation.schema import EvaluationCase

#: A prediction is ``(start, end, canonical_term)`` in original-text offsets.
Prediction = tuple[int, int, str]
Predictor = Callable[[str], tuple[Prediction, ...]]


def _f1(precision: float, recall: float) -> float:
    if precision + recall == 0.0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


@dataclass(frozen=True, slots=True)
class SliceCounts:
    """Occurrence-level tallies for one slice."""

    cases: int = 0
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0

    @property
    def precision(self) -> float:
        return _ratio(self.true_positives, self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        return _ratio(self.true_positives, self.true_positives + self.false_negatives)

    @property
    def f1(self) -> float:
        return _f1(self.precision, self.recall)


@dataclass(frozen=True, slots=True)
class CorpusReport:
    """Aggregate result of scoring a predictor against annotated cases."""

    total_cases: int
    scored_cases: int
    excluded_review_cases: int
    true_positives: int
    false_positives: int
    false_negatives: int
    sentence_true_positives: int
    sentence_false_positives: int
    sentence_false_negatives: int
    clean_cases: int
    clean_cases_with_a_detection: int
    exact_span_agreements: int
    term_mismatches: int
    per_slice: dict[str, SliceCounts] = field(default_factory=dict)
    false_positive_case_ids: tuple[str, ...] = ()
    false_negative_case_ids: tuple[str, ...] = ()

    @property
    def precision(self) -> float:
        return _ratio(self.true_positives, self.true_positives + self.false_positives)

    @property
    def recall(self) -> float:
        return _ratio(self.true_positives, self.true_positives + self.false_negatives)

    @property
    def f1(self) -> float:
        return _f1(self.precision, self.recall)

    @property
    def sentence_precision(self) -> float:
        return _ratio(
            self.sentence_true_positives,
            self.sentence_true_positives + self.sentence_false_positives,
        )

    @property
    def sentence_recall(self) -> float:
        return _ratio(
            self.sentence_true_positives,
            self.sentence_true_positives + self.sentence_false_negatives,
        )

    @property
    def sentence_f1(self) -> float:
        return _f1(self.sentence_precision, self.sentence_recall)

    @property
    def clean_false_positive_rate(self) -> float:
        """Share of sentences with no gold match where the predictor fired anyway."""

        return _ratio(self.clean_cases_with_a_detection, self.clean_cases)

    @property
    def exact_span_agreement(self) -> float:
        return _ratio(self.exact_span_agreements, self.true_positives)

    @property
    def canonical_term_agreement(self) -> float:
        """Share of detections on a gold span that also carried the gold term.

        A prediction that lands on real profanity under the wrong canonical term
        still blocks the sentence, so it is not the same defect as flagging an
        innocent one. Occurrence precision cannot tell them apart; this can.
        """

        return _ratio(self.true_positives, self.true_positives + self.term_mismatches)


def evaluate_cases(cases: Iterable[EvaluationCase], predict: Predictor) -> CorpusReport:
    """Score ``predict`` against ``cases``.

    Cases marked ``review`` are excluded from every metric but still counted, so
    an ambiguous backlog cannot quietly inflate a score.

    An occurrence counts as a true positive when a prediction carries the gold
    canonical term and overlaps its span. Exact span agreement is tracked
    separately rather than folded into the headline number.
    """

    total = 0
    scored = 0
    excluded = 0
    tp = fp = fn = 0
    sentence_tp = sentence_fp = sentence_fn = 0
    clean_cases = 0
    clean_hits = 0
    exact_spans = 0
    term_mismatches = 0
    per_slice: dict[str, dict[str, int]] = {}
    fp_ids: list[str] = []
    fn_ids: list[str] = []

    for case in cases:
        total += 1
        if case.status == "review":
            excluded += 1
            continue
        scored += 1

        predictions = list(predict(case.text))
        unmatched_expected = list(case.expected_matches)
        case_tp = case_fp = 0

        for start, end, term in predictions:
            hit = next(
                (
                    expected
                    for expected in unmatched_expected
                    if expected.canonical_term == term
                    and start < expected.end
                    and expected.start < end
                ),
                None,
            )
            if hit is None:
                case_fp += 1
                if any(
                    start < expected.end and expected.start < end
                    for expected in case.expected_matches
                ):
                    term_mismatches += 1
                continue
            unmatched_expected.remove(hit)
            case_tp += 1
            if (start, end) == (hit.start, hit.end):
                exact_spans += 1

        case_fn = len(unmatched_expected)
        tp += case_tp
        fp += case_fp
        fn += case_fn

        if case_fp:
            fp_ids.append(case.id)
        if case_fn:
            fn_ids.append(case.id)

        expected_any = bool(case.expected_matches)
        detected_any = bool(predictions)
        if expected_any and detected_any:
            sentence_tp += 1
        elif not expected_any and detected_any:
            sentence_fp += 1
        elif expected_any and not detected_any:
            sentence_fn += 1

        if not expected_any:
            clean_cases += 1
            if detected_any:
                clean_hits += 1

        for slice_name in case.slices:
            bucket = per_slice.setdefault(
                slice_name,
                {"cases": 0, "true_positives": 0, "false_positives": 0, "false_negatives": 0},
            )
            bucket["cases"] += 1
            bucket["true_positives"] += case_tp
            bucket["false_positives"] += case_fp
            bucket["false_negatives"] += case_fn

    return CorpusReport(
        total_cases=total,
        scored_cases=scored,
        excluded_review_cases=excluded,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        sentence_true_positives=sentence_tp,
        sentence_false_positives=sentence_fp,
        sentence_false_negatives=sentence_fn,
        clean_cases=clean_cases,
        clean_cases_with_a_detection=clean_hits,
        exact_span_agreements=exact_spans,
        term_mismatches=term_mismatches,
        per_slice={name: SliceCounts(**counts) for name, counts in sorted(per_slice.items())},
        false_positive_case_ids=tuple(fp_ids),
        false_negative_case_ids=tuple(fn_ids),
    )
