"""Prepare blinded matcher re-audits and safely apply adjudicated decisions."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_DECISION_FIELDS = ("label", "expected_matches", "slices", "notes")
_IMMUTABLE_CASE_FIELDS = ("id", "text", "source", "license", "split")


class ReauditWorkflowError(ValueError):
    """Raised when protected re-audit evidence cannot be processed safely."""


@dataclass(frozen=True, slots=True)
class ReauditResult:
    """A protected corpus and an aggregate-only workflow report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


def canonical_corpus_sha256(corpus: Mapping[str, Any]) -> str:
    """Return the single-document hash used by the matcher ablation runner."""

    serialized = json.dumps(
        [corpus],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def prepare_matcher_fp_reaudit(
    corpus_path: Path,
    ablation_report_path: Path,
    *,
    matcher: str,
    corpus_id: str,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> ReauditResult:
    """Reset matcher-added FP cases to blinded review without exposing prior decisions."""

    _validate_output_paths((corpus_path, ablation_report_path), output_path, report_path)
    matcher = _require_identifier(matcher, "matcher")
    corpus_id = _require_identifier(corpus_id, "corpus_id")
    source = _load_corpus(corpus_path, "source corpus")
    ablation = _read_object(ablation_report_path, "ablation report")
    _validate_ablation_source(ablation, source)
    selected_ids = _matcher_false_positive_ids(ablation, matcher)
    source_cases = cast(list[dict[str, Any]], source["cases"])
    source_by_id = {cast(str, case["id"]): case for case in source_cases}
    missing = selected_ids - source_by_id.keys()
    if missing:
        raise ReauditWorkflowError("ablation report references unknown source cases")

    selected = [copy.deepcopy(source_by_id[case_id]) for case_id in sorted(selected_ids)]
    prior_labels = Counter(cast(str, case["label"]) for case in selected)
    prior_slices = Counter(
        slice_name for case in selected for slice_name in cast(list[str], case["slices"])
    )
    for case in selected:
        case["label"] = "review"
        case["expected_matches"] = []
        case["slices"] = ["unadjudicated-intake"]
        case["notes"] = "Blinded re-audit; prior decision intentionally removed."

    corpus = {"schema_version": 1, "corpus_id": corpus_id, "cases": selected}
    report = {
        "schema_version": 1,
        "matcher": matcher,
        "source_corpus_sha256": canonical_corpus_sha256(source),
        "ablation_report_sha256": _canonical_sha256(ablation),
        "selected_count": len(selected),
        "prior_label_counts": _label_counts(prior_labels),
        "prior_slice_counts": dict(sorted(prior_slices.items())),
        "blinded": True,
        "gold_ready": False,
    }
    result = ReauditResult(corpus, report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def apply_reaudit_corpus(
    source_corpus_path: Path,
    prepared_reaudit_path: Path,
    adjudicated_reaudit_path: Path,
    adjudication_report_path: Path,
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> ReauditResult:
    """Apply only adjudicated decision fields back to the protected source corpus."""

    _validate_output_paths(
        (
            source_corpus_path,
            prepared_reaudit_path,
            adjudicated_reaudit_path,
            adjudication_report_path,
        ),
        output_path,
        report_path,
    )
    source = _load_corpus(source_corpus_path, "source corpus")
    prepared = _load_corpus(prepared_reaudit_path, "prepared re-audit corpus")
    reaudit = _load_corpus(adjudicated_reaudit_path, "adjudicated re-audit corpus")
    adjudication_report = _read_object(adjudication_report_path, "adjudication report")
    source_cases = cast(list[dict[str, Any]], source["cases"])
    prepared_cases = cast(list[dict[str, Any]], prepared["cases"])
    reaudit_cases = cast(list[dict[str, Any]], reaudit["cases"])
    if not prepared_cases or not reaudit_cases:
        raise ReauditWorkflowError("adjudicated re-audit corpus contains no cases")

    source_by_id = {cast(str, case["id"]): case for case in source_cases}
    prepared_by_id = {cast(str, case["id"]): case for case in prepared_cases}
    reaudit_by_id = {cast(str, case["id"]): case for case in reaudit_cases}
    if (
        prepared["corpus_id"] != reaudit["corpus_id"]
        or prepared_by_id.keys() != reaudit_by_id.keys()
        or not prepared_by_id.keys() <= source_by_id.keys()
    ):
        raise ReauditWorkflowError("re-audit corpus references unknown source cases")
    for case_id, prepared_case in prepared_by_id.items():
        source_case = source_by_id[case_id]
        adjudicated_case = reaudit_by_id[case_id]
        if prepared_case["label"] != "review" or any(
            prepared_case[field] != source_case[field]
            or adjudicated_case[field] != prepared_case[field]
            for field in _IMMUTABLE_CASE_FIELDS
        ):
            raise ReauditWorkflowError("re-audit modified immutable case fields")
    prepared_sha256 = _validate_adjudication_evidence(
        adjudication_report,
        prepared_reaudit_path=prepared_reaudit_path,
        prepared=prepared,
        adjudicated_cases=reaudit_cases,
    )

    updated = copy.deepcopy(source)
    updated_cases = cast(list[dict[str, Any]], updated["cases"])
    transitions: Counter[str] = Counter()
    for target in updated_cases:
        case_id = cast(str, target["id"])
        replacement = reaudit_by_id.get(case_id)
        if replacement is None:
            continue
        previous_label = cast(str, target["label"])
        replacement_label = cast(str, replacement["label"])
        transitions[f"{previous_label}->{replacement_label}"] += 1
        for field in _DECISION_FIELDS:
            target[field] = copy.deepcopy(replacement[field])

    source_counts = Counter(cast(str, case["label"]) for case in source_cases)
    updated_counts = Counter(cast(str, case["label"]) for case in updated_cases)
    report = {
        "schema_version": 1,
        "source_corpus_sha256": canonical_corpus_sha256(source),
        "prepared_reaudit_sha256": prepared_sha256,
        "adjudicated_reaudit_sha256": canonical_corpus_sha256(reaudit),
        "adjudication_report_sha256": _canonical_sha256(adjudication_report),
        "applied_count": len(reaudit_cases),
        "source_corpus_counts": _label_counts(source_counts),
        "updated_corpus_counts": _label_counts(updated_counts),
        "label_transition_counts": dict(sorted(transitions.items())),
        "gold_ready": False,
    }
    result = ReauditResult(updated, report)
    if output_path is not None:
        _write_json(output_path, updated)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _validate_adjudication_evidence(
    report: Mapping[str, Any],
    *,
    prepared_reaudit_path: Path,
    prepared: Mapping[str, Any],
    adjudicated_cases: Sequence[Mapping[str, Any]],
) -> str:
    try:
        prepared_sha256 = hashlib.sha256(prepared_reaudit_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ReauditWorkflowError("failed to hash prepared re-audit corpus") from exc
    counts = Counter(cast(str, case["label"]) for case in adjudicated_cases)
    if (
        report.get("schema_version") != 1
        or report.get("corpus_id") != prepared["corpus_id"]
        or report.get("source_corpus_sha256") != prepared_sha256
        or report.get("batch_case_count") != len(adjudicated_cases)
        or report.get("batch_counts") != _label_counts(counts)
        or report.get("gold_ready") is not False
    ):
        raise ReauditWorkflowError("adjudication evidence mismatch")
    return prepared_sha256


def _validate_ablation_source(ablation: Mapping[str, Any], corpus: Mapping[str, Any]) -> None:
    if ablation.get("schema_version") != 1:
        raise ReauditWorkflowError("ablation report version is unsupported")
    evidence = ablation.get("corpus")
    if not isinstance(evidence, dict):
        raise ReauditWorkflowError("ablation report corpus evidence is invalid")
    if evidence.get("corpus_ids") != [corpus["corpus_id"]] or evidence.get(
        "sha256"
    ) != canonical_corpus_sha256(corpus):
        raise ReauditWorkflowError("ablation report corpus evidence mismatch")


def _matcher_false_positive_ids(ablation: Mapping[str, Any], matcher: str) -> set[str]:
    rows = ablation.get("matcher_ablation")
    if not isinstance(rows, list):
        raise ReauditWorkflowError("ablation report matcher evidence is invalid")
    matches = [row for row in rows if isinstance(row, dict) and row.get("matcher") == matcher]
    if len(matches) != 1:
        raise ReauditWorkflowError("requested matcher evidence is missing or ambiguous")
    raw_ids = matches[0].get("new_false_positive_case_ids")
    if (
        not isinstance(raw_ids, list)
        or not raw_ids
        or any(not isinstance(case_id, str) for case_id in raw_ids)
        or len(set(raw_ids)) != len(raw_ids)
    ):
        raise ReauditWorkflowError("matcher false-positive case IDs are invalid")
    return set(cast(list[str], raw_ids))


def _load_corpus(path: Path, description: str) -> dict[str, Any]:
    try:
        validate_corpus_paths([path])
    except CorpusValidationError as exc:
        raise ReauditWorkflowError(f"{description} violates the corpus contract") from exc
    return _read_object(path, description)


def _label_counts(counts: Mapping[str, int]) -> dict[str, int]:
    return {label: counts.get(label, 0) for label in ("positive", "hard-negative", "review")}


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise ReauditWorkflowError(f"{name} is invalid")
    return value


def _validate_output_paths(
    inputs: Sequence[Path], output_path: Path | None, report_path: Path | None
) -> None:
    resolved_inputs = {path.resolve() for path in inputs}
    outputs = [path.resolve() for path in (output_path, report_path) if path is not None]
    if any(path in resolved_inputs for path in outputs) or len(set(outputs)) != len(outputs):
        raise ReauditWorkflowError("workflow outputs must not overwrite inputs or each other")


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReauditWorkflowError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise ReauditWorkflowError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReauditWorkflowError("failed to write workflow output") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare", help="prepare a blinded matcher FP re-audit")
    prepare.add_argument("corpus", type=Path)
    prepare.add_argument("ablation", type=Path)
    prepare.add_argument("--matcher", required=True)
    prepare.add_argument("--corpus-id", required=True)
    prepare.add_argument("--output", required=True, type=Path)
    prepare.add_argument("--report", required=True, type=Path)
    apply_parser = subparsers.add_parser("apply", help="apply an adjudicated re-audit")
    apply_parser.add_argument("source", type=Path)
    apply_parser.add_argument("prepared", type=Path)
    apply_parser.add_argument("adjudicated", type=Path)
    apply_parser.add_argument("adjudication_report", type=Path)
    apply_parser.add_argument("--output", required=True, type=Path)
    apply_parser.add_argument("--report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the protected workflow while printing aggregate counts only."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.command == "prepare":
            result = prepare_matcher_fp_reaudit(
                arguments.corpus,
                arguments.ablation,
                matcher=arguments.matcher,
                corpus_id=arguments.corpus_id,
                output_path=arguments.output,
                report_path=arguments.report,
            )
            print(f"selected={result.report['selected_count']}; blinded=true; gold_ready=false")
        else:
            result = apply_reaudit_corpus(
                arguments.source,
                arguments.prepared,
                arguments.adjudicated,
                arguments.adjudication_report,
                output_path=arguments.output,
                report_path=arguments.report,
            )
            print(f"applied={result.report['applied_count']}; gold_ready=false")
    except ReauditWorkflowError as exc:
        print(f"re-audit workflow failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
