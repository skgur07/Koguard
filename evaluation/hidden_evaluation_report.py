"""Sanitize a protected ablation into aggregate-only hidden release evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from evaluation.profile_report import ProfileReportError, build_profile_report
from evaluation.split_guard import NORMALIZATION_VERSION

HIDDEN_ATTESTATION_SCHEMA_PATH = Path(__file__).with_name(
    "hidden-evaluation-attestation.schema.json"
)
HIDDEN_EVALUATION_REPORT_SCHEMA_PATH = Path(__file__).with_name(
    "hidden-evaluation-report.schema.json"
)
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_STABLE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_ATTESTATION_FIELDS = frozenset(
    {
        "schema_version",
        "evaluation_id",
        "evaluation_version",
        "release_commit",
        "protected_ablation_report_sha256",
        "manifest",
        "corpus",
        "review",
    }
)
_MANIFEST_FIELDS = frozenset(
    {
        "manifest_id",
        "manifest_version",
        "normalization_version",
        "direct_leak_count",
        "normalized_leak_count",
    }
)
_CORPUS_FIELDS = frozenset(
    {
        "sha256",
        "case_count",
        "positive_count",
        "hard_negative_count",
        "excluded_review_count",
    }
)
_REVIEW_FIELDS = frozenset(
    {
        "annotation_status",
        "privacy_review_complete",
        "rights_review_complete",
        "custodian_approval_id",
        "release_reviewer_approval_id",
    }
)


class HiddenEvaluationReportError(ValueError):
    """Raised when protected evidence cannot produce a safe hidden report."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise HiddenEvaluationReportError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise HiddenEvaluationReportError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise HiddenEvaluationReportError(f"{label} must be a non-empty string")
    return value


def _stable_id(value: object, label: str) -> str:
    identifier = _string(value, label)
    if _STABLE_ID_PATTERN.fullmatch(identifier) is None:
        raise HiddenEvaluationReportError(f"{label} must be a stable identifier")
    return identifier


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise HiddenEvaluationReportError(f"{label} must be an integer of at least {minimum}")
    return value


def _boolean(value: object, label: str) -> bool:
    if not isinstance(value, bool):
        raise HiddenEvaluationReportError(f"{label} must be a boolean")
    return value


def _sha256(value: object, label: str) -> str:
    digest = _string(value, label)
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise HiddenEvaluationReportError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _release_commit(value: object) -> str:
    commit = _string(value, "release_commit")
    if _COMMIT_PATTERN.fullmatch(commit) is None:
        raise HiddenEvaluationReportError("release_commit must be a full lowercase Git SHA")
    return commit


def _require_closed_fields(value: Mapping[str, Any], allowed: frozenset[str], label: str) -> None:
    actual = set(value)
    if actual != allowed:
        raise HiddenEvaluationReportError(f"{label} fields do not match the closed contract")


def _metric(value: object, label: str, *, sentence: bool) -> dict[str, Any]:
    metric = _object(value, label)
    counts = _object(metric.get("counts"), f"{label}.counts")
    count_names = ("tp", "fp", "fn", "tn") if sentence else ("tp", "fp", "fn")
    sanitized_counts = {
        name: _integer(counts.get(name), f"{label}.counts.{name}") for name in count_names
    }
    rate_names = (
        ("precision", "recall", "f1", "accuracy")
        if sentence
        else (
            "precision",
            "recall",
            "f1",
        )
    )
    sanitized: dict[str, Any] = {"counts": sanitized_counts}
    for name in rate_names:
        rate = metric.get(name)
        if rate is not None and (
            isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not math.isfinite(rate)
            or not 0 <= rate <= 1
        ):
            raise HiddenEvaluationReportError(f"{label}.{name} must be a rate or null")
        sanitized[name] = float(rate) if rate is not None else None
    return sanitized


def _balanced_slice_metrics(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    for raw_profile in _array(source.get("profiles"), "profiles"):
        profile = _object(raw_profile, "profile")
        if profile.get("profile_id") != "choseong":
            continue
        sanitized: list[dict[str, Any]] = []
        for raw_slice in _array(profile.get("slice_metrics"), "choseong.slice_metrics"):
            slice_metric = _object(raw_slice, "slice metric")
            sanitized.append(
                {
                    "slice": _stable_id(slice_metric.get("slice"), "slice metric.slice"),
                    "case_count": _integer(
                        slice_metric.get("case_count"), "slice metric.case_count", minimum=1
                    ),
                    "sentence_metrics": _metric(
                        slice_metric.get("sentence_metrics"),
                        "slice metric.sentence_metrics",
                        sentence=True,
                    ),
                    "occurrence_metrics": _metric(
                        slice_metric.get("occurrence_metrics"),
                        "slice metric.occurrence_metrics",
                        sentence=False,
                    ),
                }
            )
        if not sanitized:
            raise HiddenEvaluationReportError("balanced profile must contain slice metrics")
        return sanitized
    raise HiddenEvaluationReportError("protected ablation is missing the balanced source profile")


def _validated_attestation(
    attestation: Mapping[str, Any],
    *,
    source: Mapping[str, Any],
    source_sha256: str,
) -> dict[str, Any]:
    _require_closed_fields(attestation, _ATTESTATION_FIELDS, "attestation")
    if attestation.get("schema_version") != 1:
        raise HiddenEvaluationReportError("attestation schema_version must equal 1")
    evaluation_id = _stable_id(attestation.get("evaluation_id"), "evaluation_id")
    evaluation_version = _integer(
        attestation.get("evaluation_version"), "evaluation_version", minimum=1
    )
    release_commit = _release_commit(attestation.get("release_commit"))
    bound_source_sha256 = _sha256(
        attestation.get("protected_ablation_report_sha256"),
        "protected_ablation_report_sha256",
    )
    if bound_source_sha256 != source_sha256:
        raise HiddenEvaluationReportError("attestation is not bound to the protected report")

    manifest = _object(attestation.get("manifest"), "manifest")
    _require_closed_fields(manifest, _MANIFEST_FIELDS, "manifest")
    manifest_id = _stable_id(manifest.get("manifest_id"), "manifest.manifest_id")
    manifest_version = _integer(
        manifest.get("manifest_version"), "manifest.manifest_version", minimum=1
    )
    if manifest.get("normalization_version") != NORMALIZATION_VERSION:
        raise HiddenEvaluationReportError("manifest normalization version is unsupported")
    direct_leaks = _integer(manifest.get("direct_leak_count"), "manifest.direct_leak_count")
    normalized_leaks = _integer(
        manifest.get("normalized_leak_count"), "manifest.normalized_leak_count"
    )
    if direct_leaks or normalized_leaks:
        raise HiddenEvaluationReportError("hidden evaluation leak counts must both be zero")

    source_corpus = _object(source.get("corpus"), "source.corpus")
    attested_corpus = _object(attestation.get("corpus"), "attestation.corpus")
    _require_closed_fields(attested_corpus, _CORPUS_FIELDS, "attestation.corpus")
    corpus_evidence = {
        "sha256": _sha256(attested_corpus.get("sha256"), "attestation.corpus.sha256"),
        "case_count": _integer(
            attested_corpus.get("case_count"), "attestation.corpus.case_count", minimum=2
        ),
        "positive_count": _integer(
            attested_corpus.get("positive_count"),
            "attestation.corpus.positive_count",
            minimum=1,
        ),
        "hard_negative_count": _integer(
            attested_corpus.get("hard_negative_count"),
            "attestation.corpus.hard_negative_count",
            minimum=1,
        ),
        "excluded_review_count": _integer(
            attested_corpus.get("excluded_review_count"),
            "attestation.corpus.excluded_review_count",
        ),
    }
    source_evidence = {
        key: source_corpus.get(key)
        for key in (
            "sha256",
            "case_count",
            "positive_count",
            "hard_negative_count",
            "excluded_review_count",
        )
    }
    if corpus_evidence != source_evidence:
        raise HiddenEvaluationReportError(
            "attested corpus evidence does not match protected report"
        )
    if corpus_evidence["excluded_review_count"] != 0:
        raise HiddenEvaluationReportError(
            "hidden evaluation cannot contain unresolved review cases"
        )
    if cast(int, corpus_evidence["case_count"]) != (
        cast(int, corpus_evidence["positive_count"])
        + cast(int, corpus_evidence["hard_negative_count"])
    ):
        raise HiddenEvaluationReportError("hidden corpus counts are inconsistent")

    review = _object(attestation.get("review"), "review")
    _require_closed_fields(review, _REVIEW_FIELDS, "review")
    if review.get("annotation_status") != "independent-consensus":
        raise HiddenEvaluationReportError("hidden annotations must have independent consensus")
    if not _boolean(review.get("privacy_review_complete"), "review.privacy_review_complete"):
        raise HiddenEvaluationReportError("hidden privacy review must be complete")
    if not _boolean(review.get("rights_review_complete"), "review.rights_review_complete"):
        raise HiddenEvaluationReportError("hidden rights review must be complete")
    custodian = _stable_id(review.get("custodian_approval_id"), "review.custodian_approval_id")
    release_reviewer = _stable_id(
        review.get("release_reviewer_approval_id"), "review.release_reviewer_approval_id"
    )
    if custodian == release_reviewer:
        raise HiddenEvaluationReportError(
            "custodian and release reviewer approvals must be distinct"
        )

    return {
        "evaluation_id": evaluation_id,
        "evaluation_version": evaluation_version,
        "release_commit": release_commit,
        "manifest_id": manifest_id,
        "manifest_version": manifest_version,
        "corpus": corpus_evidence,
    }


def build_hidden_evaluation_report(
    source: Mapping[str, Any],
    *,
    source_sha256: str,
    attestation: Mapping[str, Any],
    attestation_sha256: str,
) -> dict[str, Any]:
    """Return hidden evaluation evidence with no case, text, or canonical identifiers."""

    source_digest = _sha256(source_sha256, "source_sha256")
    attestation_digest = _sha256(attestation_sha256, "attestation_sha256")
    attested = _validated_attestation(
        attestation,
        source=source,
        source_sha256=source_digest,
    )
    try:
        profile_report = build_profile_report(source, source_sha256=source_digest)
    except ProfileReportError as exc:
        raise HiddenEvaluationReportError(str(exc)) from exc
    source_payload = _object(profile_report.get("source"), "sanitized source")
    source_corpus = _object(source_payload.get("corpus"), "sanitized source.corpus")
    hidden_corpus = {
        **{
            key: source_corpus[key]
            for key in (
                "sha256",
                "case_count",
                "positive_count",
                "hard_negative_count",
                "excluded_review_count",
            )
        },
        "classification": "independent-hidden-evaluation",
        "gold_ready": True,
    }
    return {
        "schema_version": 1,
        "report_kind": "hidden-evaluation",
        "release_commit": attested["release_commit"],
        "evaluation": {
            "evaluation_id": attested["evaluation_id"],
            "evaluation_version": attested["evaluation_version"],
            "manifest_id": attested["manifest_id"],
            "manifest_version": attested["manifest_version"],
            "normalization_version": NORMALIZATION_VERSION,
            "attestation_sha256": attestation_digest,
            "approval_count": 2,
            "direct_leak_count": 0,
            "normalized_leak_count": 0,
            "gold_ready": True,
        },
        "source": {
            "protected_ablation_report_sha256": source_digest,
            "measured_at": source_payload["measured_at"],
            "corpus": hidden_corpus,
            "environment": source_payload["environment"],
        },
        "profiles": profile_report["profiles"],
        "balanced_evidence": profile_report["balanced_evidence"],
        "balanced_gates": profile_report["balanced_gates"],
        "balanced_slice_metrics": _balanced_slice_metrics(source),
        "limitations": [
            "이 보고서는 보호된 hidden evaluation의 원문·case ID·canonical term을 포함하지 않는다.",
            (
                "수치는 고정된 lexical core와 profile만 평가하며 "
                "향후 선택적 AI 성능을 포함하지 않는다."
            ),
            (
                "실패 사례는 slice별 집계로만 tuning 작업에 전달하고 "
                "이 hidden version에 재사용하지 않는다."
            ),
        ],
    }


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HiddenEvaluationReportError(f"failed to read {label}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ablation", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write an aggregate-only hidden evaluation report."""

    arguments = _parser().parse_args(argv)
    try:
        resolved_inputs = {
            arguments.source_ablation.resolve(),
            arguments.attestation.resolve(),
        }
        if arguments.output.resolve() in resolved_inputs:
            raise HiddenEvaluationReportError("output must not overwrite protected evidence")
        source = _load_object(arguments.source_ablation, "protected ablation report")
        attestation = _load_object(arguments.attestation, "hidden attestation")
        report = build_hidden_evaluation_report(
            source,
            source_sha256=_hash_file(arguments.source_ablation),
            attestation=attestation,
            attestation_sha256=_hash_file(arguments.attestation),
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        corpus = _object(_object(report["source"], "source")["corpus"], "source.corpus")
        print(
            "hidden evaluation aggregate written; "
            f"cases={corpus['case_count']}; positive={corpus['positive_count']}; "
            f"hard_negative={corpus['hard_negative_count']}; leaks=0"
        )
    except HiddenEvaluationReportError as exc:
        print(f"hidden evaluation report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
