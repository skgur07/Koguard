"""Run Koguard against the evaluation corpus and print a slice-aware report."""

import argparse
from collections.abc import Sequence

from evaluation.loader import load_all_cases, load_split
from evaluation.report import CorpusReport, Prediction, Predictor, evaluate_cases
from evaluation.schema import EvaluationCase, Split
from koguard import EngineConfig, KoguardDictionary, KoguardEngine

#: The presets a release decision is measured against, per plan section 6.5.
PRESETS: dict[str, EngineConfig] = {
    "strict": EngineConfig.strict(),
    "balanced": EngineConfig.balanced(),
    "aggressive": EngineConfig.aggressive(),
}


def predictor_for(engine: KoguardEngine) -> Predictor:
    """Adapt ``engine`` to the predictor signature used by :func:`evaluate_cases`.

    A match without a span carries no position to score against gold offsets, so
    it is skipped rather than guessed at.
    """

    def predict(text: str) -> tuple[Prediction, ...]:
        return tuple(
            (match.start, match.end, match.term)
            for match in engine.check(text).matches
            if match.start is not None and match.end is not None
        )

    return predict


def measure(
    cases: Sequence[EvaluationCase],
    config: EngineConfig | None = None,
    *,
    include_contextual: bool = False,
) -> CorpusReport:
    resolved_config = EngineConfig() if config is None else config
    engine = KoguardEngine(
        config=resolved_config,
        dictionary=KoguardDictionary.default(
            resolved_config.unicode_form,
            include_contextual=include_contextual,
        ),
    )
    return evaluate_cases(cases, predict=predictor_for(engine))


def format_report(report: CorpusReport) -> str:
    lines = [
        f"cases              {report.total_cases} "
        f"(scored {report.scored_cases}, review {report.excluded_review_cases})",
        f"occurrence         TP={report.true_positives} "
        f"FP={report.false_positives} FN={report.false_negatives}",
        f"                   P={report.precision:.4f} R={report.recall:.4f} F1={report.f1:.4f}",
        f"sentence           P={report.sentence_precision:.4f} "
        f"R={report.sentence_recall:.4f} F1={report.sentence_f1:.4f}",
        f"clean FP rate      {report.clean_false_positive_rate:.4%} "
        f"({report.clean_cases_with_a_detection}/{report.clean_cases})",
        f"exact span         {report.exact_span_agreement:.4f}",
        f"canonical term     {report.canonical_term_agreement:.4f} "
        f"(mismatched {report.term_mismatches})",
        "",
        f"{'slice':<22}{'n':>5}{'TP':>5}{'FP':>5}{'FN':>5}{'P':>9}{'R':>9}",
    ]
    for name, counts in report.per_slice.items():
        lines.append(
            f"{name:<22}{counts.cases:>5}{counts.true_positives:>5}"
            f"{counts.false_positives:>5}{counts.false_negatives:>5}"
            f"{counts.precision:>9.4f}{counts.recall:>9.4f}"
        )
    if report.false_positive_case_ids:
        lines += ["", "false positives:"]
        lines += [f"  {case_id}" for case_id in report.false_positive_case_ids]
    if report.false_negative_case_ids:
        lines += ["", "false negatives:"]
        lines += [f"  {case_id}" for case_id in report.false_negative_case_ids]
    return "\n".join(lines)


#: Stages the default enables, each paired with a config that switches only that
#: stage off. Spelled out rather than built from strings so a wrong flag name is
#: a type error instead of a silently ineffective run.
MATCHER_ABLATIONS: tuple[tuple[str, EngineConfig], ...] = (
    ("exact_matching", EngineConfig(exact_matching=False)),
    ("repeated_matching", EngineConfig(repeated_matching=False)),
    ("separator_matching", EngineConfig(separator_matching=False)),
    ("whitespace_gap_matching", EngineConfig(whitespace_gap_matching=False)),
    ("mixed_gap_matching", EngineConfig(mixed_gap_matching=False)),
    ("choseong_matching", EngineConfig(choseong_matching=False)),
    ("alias_matching", EngineConfig(alias_matching=False)),
    ("keyboard_matching", EngineConfig(keyboard_matching=False)),
    ("jamo_composition_matching", EngineConfig(jamo_composition_matching=False)),
    ("segmented_input_matching", EngineConfig(segmented_input_matching=False)),
)

#: What the default leaves off. Removing a stage that is already off measures
#: nothing, so these are reported in the direction a caller would move them.
MATCHER_ADDITIONS: tuple[tuple[str, EngineConfig, bool], ...] = (
    ("fuzzy_matching", EngineConfig(fuzzy_matching=True), False),
    ("contextual tier", EngineConfig(), True),
)


def ablate(cases: Sequence[EvaluationCase]) -> str:
    """Report what each stage is worth, measured against the default.

    Enabled stages are measured by switching one off; stages the default leaves
    off are measured by switching one on. Both directions are reported against
    the same baseline so the numbers can be compared to each other.
    """

    baseline = measure(cases)
    lines = [
        f"{'change from the default':<28}{'TP':>5}{'FP':>5}{'FN':>5}{'dTP':>6}{'dFP':>6}",
        f"{'(baseline, balanced)':<28}"
        f"{baseline.true_positives:>5}{baseline.false_positives:>5}"
        f"{baseline.false_negatives:>5}{'':>6}{'':>6}",
    ]

    def row(label: str, config: EngineConfig, contextual: bool) -> str:
        report = measure(cases, config=config, include_contextual=contextual)
        return (
            f"{label:<28}{report.true_positives:>5}{report.false_positives:>5}"
            f"{report.false_negatives:>5}"
            f"{report.true_positives - baseline.true_positives:>+6}"
            f"{report.false_positives - baseline.false_positives:>+6}"
        )

    for flag, config in MATCHER_ABLATIONS:
        lines.append(row(f"-{flag}", config, False))
    for flag, config, contextual in MATCHER_ADDITIONS:
        lines.append(row(f"+{flag}", config, contextual))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--split",
        choices=("tuning", "evaluation", "all"),
        default="tuning",
        help="corpus split to score; 'all' merges both",
    )
    parser.add_argument(
        "--ablation",
        action="store_true",
        help="also report what removing each matcher stage costs",
    )
    parser.add_argument(
        "--preset",
        choices=tuple(PRESETS),
        default="balanced",
        help="preset to score; 'balanced' is what KoguardEngine() resolves to",
    )
    parser.add_argument(
        "--contextual",
        action="store_true",
        help="add the contextual dictionary tier, as 'aggressive' callers may",
    )
    args = parser.parse_args(argv)

    if args.split == "all":
        cases: Sequence[EvaluationCase] = load_all_cases()
    else:
        split: Split = args.split
        cases = load_split(split)

    print(f"# split: {args.split}  preset: {args.preset}  contextual: {args.contextual}")
    print(
        format_report(
            measure(
                cases,
                config=PRESETS[args.preset],
                include_contextual=args.contextual,
            )
        )
    )
    if args.ablation:
        print()
        print(ablate(cases))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
