"""Evaluate approved literal candidates against protected tuning gold."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths
from koguard import KoguardDictionary, KoguardEngine

FN_CANDIDATE_REPORT_SCHEMA_PATH = Path(__file__).with_name("fn-candidate-report.schema.json")
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class FnCandidateEvaluationError(ValueError):
    """Raised when a candidate evaluation input violates the safe contract."""


@dataclass(frozen=True, slots=True)
class _Candidate:
    candidate_id: str
    surface: str
    canonical: str


@dataclass(frozen=True, slots=True)
class _Metrics:
    sentence: dict[str, int]
    occurrence: dict[str, int]


def evaluate_fn_candidates(corpus_path: Path, manifest_path: Path) -> dict[str, Any]:
    """Compare approved literal candidates with the packaged aggressive baseline."""

    try:
        validate_corpus_paths([corpus_path])
    except CorpusValidationError as exc:
        raise FnCandidateEvaluationError("input corpus violates the corpus contract") from exc
    corpus = _read_object(corpus_path, "corpus")
    manifest = _read_object(manifest_path, "candidate manifest")
    candidates = _load_candidates(manifest)
    cases = cast(list[dict[str, Any]], corpus["cases"])
    evaluated = tuple(case for case in cases if case["label"] != "review")
    positive_cases = tuple(case for case in evaluated if case["label"] == "positive")
    hard_negative_count = sum(case["label"] == "hard-negative" for case in evaluated)
    if not positive_cases:
        raise FnCandidateEvaluationError("corpus contains no positive cases")

    baseline = _evaluate(KoguardEngine(profile="aggressive"), evaluated)
    individual: list[dict[str, Any]] = []
    for candidate in candidates:
        metrics = _evaluate(_candidate_engine((candidate,)), evaluated)
        positive_support = _positive_support(positive_cases, {candidate.canonical})
        sentence_tp_delta = metrics.sentence["tp"] - baseline.sentence["tp"]
        sentence_fp_delta = metrics.sentence["fp"] - baseline.sentence["fp"]
        occurrence_tp_delta = metrics.occurrence["tp"] - baseline.occurrence["tp"]
        occurrence_fp_delta = metrics.occurrence["fp"] - baseline.occurrence["fp"]
        individual.append(
            {
                "candidate_id": candidate.candidate_id,
                "positive_case_support": positive_support,
                "hard_negative_case_support": hard_negative_count,
                "sentence_tp_delta": sentence_tp_delta,
                "sentence_fp_delta": sentence_fp_delta,
                "occurrence_tp_delta": occurrence_tp_delta,
                "occurrence_fp_delta": occurrence_fp_delta,
                "tuning_gate_passed": (
                    positive_support >= 1
                    and hard_negative_count >= 2
                    and occurrence_tp_delta >= 1
                    and sentence_fp_delta == 0
                    and occurrence_tp_delta > occurrence_fp_delta
                ),
            }
        )

    combined = _evaluate(_candidate_engine(candidates), evaluated)
    candidate_canonicals = {candidate.canonical for candidate in candidates}
    combined_positive_support = _positive_support(positive_cases, candidate_canonicals)
    combined_sentence_delta = _delta(combined.sentence, baseline.sentence)
    combined_occurrence_delta = _delta(combined.occurrence, baseline.occurrence)
    return {
        "schema_version": 1,
        "inputs": {
            "corpus_sha256": _sha256(corpus_path),
            "candidate_manifest_sha256": _sha256(manifest_path),
        },
        "corpus": {
            "case_count": len(evaluated),
            "positive_count": len(positive_cases),
            "hard_negative_count": hard_negative_count,
            "excluded_review_count": len(cases) - len(evaluated),
        },
        "baseline": {
            "sentence_counts": baseline.sentence,
            "occurrence_counts": baseline.occurrence,
        },
        "combined_candidate": {
            "sentence_counts": combined.sentence,
            "occurrence_counts": combined.occurrence,
            "sentence_delta": combined_sentence_delta,
            "occurrence_delta": combined_occurrence_delta,
            "positive_case_support": combined_positive_support,
            "hard_negative_case_support": hard_negative_count,
            "tuning_gate_passed": all(item["tuning_gate_passed"] for item in individual)
            and combined_sentence_delta["fp"] == 0
            and combined_occurrence_delta["tp"] > combined_occurrence_delta["fp"],
        },
        "candidates": individual,
    }


def _load_candidates(manifest: Mapping[str, Any]) -> tuple[_Candidate, ...]:
    raw_candidates = manifest.get("candidates")
    raw_sources = manifest.get("sources")
    if not isinstance(raw_candidates, list) or not isinstance(raw_sources, list):
        raise FnCandidateEvaluationError("candidate manifest structure is invalid")
    approved_sources = {
        source.get("source_id")
        for source in raw_sources
        if isinstance(source, dict)
        and source.get("license_status") == "approved"
        and source.get("redistribution_allowed") is True
    }
    candidates: list[_Candidate] = []
    seen_ids: set[str] = set()
    seen_surfaces: set[str] = set()
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict) or raw_candidate.get("status") != "candidate":
            continue
        review = raw_candidate.get("review")
        if not (
            raw_candidate.get("target_layer") == "core"
            and raw_candidate.get("classification") == "positive"
            and raw_candidate.get("representation") == "literal"
            and raw_candidate.get("matcher") == "exact"
            and raw_candidate.get("source_id") in approved_sources
            and isinstance(review, dict)
            and review.get("status") == "approved"
        ):
            continue
        candidate_id = raw_candidate.get("candidate_id")
        surface = raw_candidate.get("normalized_surface")
        canonical = raw_candidate.get("normalized_canonical")
        if (
            not isinstance(candidate_id, str)
            or _ID_PATTERN.fullmatch(candidate_id) is None
            or not isinstance(surface, str)
            or not surface
            or not isinstance(canonical, str)
            or not canonical
            or surface != canonical
        ):
            raise FnCandidateEvaluationError("candidate metadata is invalid")
        if candidate_id in seen_ids or surface in seen_surfaces:
            raise FnCandidateEvaluationError("candidate IDs and surfaces must be unique")
        seen_ids.add(candidate_id)
        seen_surfaces.add(surface)
        candidates.append(_Candidate(candidate_id, surface, canonical))
    if not candidates:
        raise FnCandidateEvaluationError("manifest contains no eligible candidates")
    return tuple(sorted(candidates, key=lambda candidate: candidate.candidate_id))


def _candidate_engine(candidates: Sequence[_Candidate]) -> KoguardEngine:
    dictionary = KoguardDictionary.from_sources(
        blacklist=(candidate.surface for candidate in candidates),
    )
    return KoguardEngine(profile="aggressive", dictionary=dictionary)


def _evaluate(engine: KoguardEngine, cases: Sequence[dict[str, Any]]) -> _Metrics:
    sentence = {key: 0 for key in ("tp", "fp", "fn", "tn")}
    occurrence = {key: 0 for key in ("tp", "fp", "fn")}
    for case in cases:
        result = engine.check(cast(str, case["text"]))
        positive = case["label"] == "positive"
        if positive:
            sentence["tp" if result.detected else "fn"] += 1
        else:
            sentence["fp" if result.detected else "tn"] += 1
        gold = {
            (match["start"], match["end"], match["canonical_term"])
            for match in cast(list[dict[str, Any]], case["expected_matches"])
        }
        predicted = {
            (match.start, match.end, match.term)
            for match in result.matches
            if match.start is not None and match.end is not None
        }
        occurrence["tp"] += len(gold & predicted)
        occurrence["fp"] += len(predicted - gold)
        occurrence["fn"] += len(gold - predicted)
    return _Metrics(sentence, occurrence)


def _positive_support(cases: Sequence[dict[str, Any]], canonicals: set[str]) -> int:
    return sum(
        any(
            match["canonical_term"] in canonicals
            for match in cast(list[dict[str, Any]], case["expected_matches"])
        )
        for case in cases
    )


def _delta(current: Mapping[str, int], baseline: Mapping[str, int]) -> dict[str, int]:
    return {key: current[key] - baseline[key] for key in baseline}


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FnCandidateEvaluationError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise FnCandidateEvaluationError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _sha256(path: Path) -> str:
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise FnCandidateEvaluationError("failed to hash evaluation input") from exc
    canonical_lf = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(canonical_lf).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run candidate evaluation and print aggregate deltas only."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.output.resolve() in {
            arguments.corpus.resolve(),
            arguments.manifest.resolve(),
        }:
            raise FnCandidateEvaluationError("output must not overwrite an input")
        report = evaluate_fn_candidates(arguments.corpus, arguments.manifest)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        combined = cast(dict[str, Any], report["combined_candidate"])
        sentence = cast(dict[str, int], combined["sentence_delta"])
        occurrence = cast(dict[str, int], combined["occurrence_delta"])
        print(
            f"candidates={len(report['candidates'])}; sentence_tp_delta={sentence['tp']}; "
            f"sentence_fp_delta={sentence['fp']}; occurrence_tp_delta={occurrence['tp']}; "
            f"occurrence_fp_delta={occurrence['fp']}"
        )
    except (FnCandidateEvaluationError, OSError, UnicodeError) as exc:
        print(f"candidate evaluation failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
