"""Combine PF-014 evidence into a deterministic release decision report."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from evaluation.profile_report import _config_settings as _profile_config_settings

from koguard import ProfileName
from release.artifact_audit import ReleaseAuditError, validate_rights_manifest_payload
from release.github_actions_evidence import (
    GitHubActionsEvidenceError,
    fetch_github_actions_evidence,
)

RELEASE_REPORT_SCHEMA_PATH = Path(__file__).with_name("release-report.schema.json")
TESTPYPI_EVIDENCE_SCHEMA_PATH = Path(__file__).with_name("testpypi-evidence.schema.json")
CI_EVIDENCE_SCHEMA_PATH = Path(__file__).with_name("ci-evidence.schema.json")
RIGHTS_MANIFEST_SCHEMA_PATH = Path(__file__).with_name("rights-manifest.schema.json")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_JOBS: tuple[tuple[str, str], ...] = (
    ("ubuntu-latest", "ubuntu-latest / CPython 3.11.9"),
    ("windows-latest", "windows-latest / CPython 3.11.9"),
    ("macos-latest", "macos-latest / CPython 3.11.9"),
)
_EXPECTED_FILENAMES = {
    "wheel": "koguard-0.1.0-py3-none-any.whl",
    "sdist": "koguard-0.1.0.tar.gz",
}
_TESTPYPI_FIELDS = frozenset(
    {
        "schema_version",
        "index_url",
        "project_url",
        "package",
        "tested_at",
        "python_version",
        "metadata_verified",
        "artifacts",
    }
)
_TESTPYPI_ARTIFACT_FIELDS = frozenset({"kind", "sha256", "smoke_passed"})
_PUBLIC_CONTRACT_FIELDS = (
    "public_api_frozen",
    "readme_claims_reviewed",
    "limitations_documented",
    "core_ai_scope_separated",
    "private_vulnerability_reporting_enabled",
)
_ARTIFACT_AUDIT_FIELDS = frozenset(
    {"schema_version", "generated_at", "source", "environment", "package", "artifacts"}
)
_ARTIFACT_SOURCE_FIELDS = frozenset({"release_commit", "git_tree"})
_ARTIFACT_ENVIRONMENT_FIELDS = frozenset({"python_version", "implementation", "platform"})
_ARTIFACT_FIELDS = {
    "wheel": frozenset(
        {"kind", "filename", "size_bytes", "sha256", "member_count", "bundled_notices"}
    ),
    "sdist": frozenset(
        {"kind", "filename", "size_bytes", "sha256", "member_count", "release_evidence"}
    ),
}
_CI_FIELDS = frozenset(
    {
        "schema_version",
        "provider",
        "repository",
        "workflow",
        "run_id",
        "run_attempt",
        "run_url",
        "head_sha",
        "event",
        "conclusion",
        "verified_at",
        "jobs",
    }
)
_CI_JOB_FIELDS = frozenset({"job_id", "name", "runner", "conclusion"})
_HIDDEN_FIELDS = frozenset(
    {
        "schema_version",
        "report_kind",
        "release_commit",
        "evaluation",
        "source",
        "profiles",
        "balanced_evidence",
        "balanced_gates",
        "balanced_slice_metrics",
        "limitations",
    }
)
_HIDDEN_EVALUATION_FIELDS = frozenset(
    {
        "evaluation_id",
        "evaluation_version",
        "manifest_id",
        "manifest_version",
        "normalization_version",
        "attestation_sha256",
        "evaluated_artifact",
        "approval_count",
        "direct_leak_count",
        "normalized_leak_count",
        "gold_ready",
    }
)
_EVALUATED_ARTIFACT_FIELDS = frozenset({"kind", "sha256"})
_HIDDEN_SOURCE_FIELDS = frozenset(
    {"protected_ablation_report_sha256", "measured_at", "corpus", "environment"}
)
_HIDDEN_CORPUS_FIELDS = frozenset(
    {
        "classification",
        "sha256",
        "case_count",
        "positive_count",
        "hard_negative_count",
        "excluded_review_count",
        "gold_ready",
    }
)
_HIDDEN_ENVIRONMENT_FIELDS = frozenset(
    {"koguard_version", "python_version", "implementation", "platform", "processor"}
)
_PROFILE_FIELDS = frozenset(
    {
        "profile",
        "source_profile_id",
        "settings",
        "sentence_metrics",
        "occurrence_metrics",
        "performance",
    }
)
_SENTENCE_METRIC_FIELDS = frozenset({"counts", "precision", "recall", "f1", "accuracy"})
_OCCURRENCE_METRIC_FIELDS = frozenset({"counts", "precision", "recall", "f1"})
_SENTENCE_COUNT_FIELDS = frozenset({"tp", "fp", "fn", "tn"})
_OCCURRENCE_COUNT_FIELDS = frozenset({"tp", "fp", "fn"})
_PERFORMANCE_FIELDS = frozenset({"short_chat", "maximum_input", "engine_retained_memory_bytes"})
_WORKLOAD_FIELDS = frozenset({"input_length", "p50_ms", "p95_ms"})
_BALANCED_EVIDENCE_FIELDS = frozenset(
    {
        "sentence_tp_delta_vs_strict",
        "sentence_fp_delta_vs_strict",
        "occurrence_tp_delta_vs_strict",
        "occurrence_fp_delta_vs_strict",
    }
)
_BALANCED_GATE_FIELDS = frozenset(
    {
        "normal_sentence_fp_rate",
        "normal_sentence_fp_rate_limit",
        "short_chat_p95_ms",
        "short_chat_p95_ms_limit",
        "maximum_input_p95_ms",
        "maximum_input_p95_ms_limit",
        "passed",
    }
)
_SLICE_FIELDS = frozenset({"slice", "case_count", "sentence_metrics", "occurrence_metrics"})
_PROFILE_SOURCE_IDS = {
    "strict": "exact-alias",
    "balanced": "choseong",
    "aggressive": "all-enabled",
}


class ReleaseReportError(ValueError):
    """Raised when release evidence is malformed or unsafe."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReleaseReportError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _array(value: object, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReleaseReportError(f"{label} must be an array")
    return value


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ReleaseReportError(f"{label} must be a non-empty string")
    return value


def _sha256(value: object, label: str) -> str:
    digest = _string(value, label)
    if _SHA256_PATTERN.fullmatch(digest) is None:
        raise ReleaseReportError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _release_commit(value: object) -> str:
    commit = _string(value, "release_commit")
    if _COMMIT_PATTERN.fullmatch(commit) is None:
        raise ReleaseReportError("release_commit must be a full lowercase Git SHA")
    return commit


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def _timestamp(value: object, label: str) -> str:
    timestamp = _string(value, label)
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ReleaseReportError(f"{label} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ReleaseReportError(f"{label} must include timezone information")
    return timestamp


def _closed(value: Mapping[str, Any], fields: frozenset[str], label: str) -> None:
    if set(value) != fields:
        raise ReleaseReportError(f"{label} fields do not match the closed contract")


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise ReleaseReportError(f"{label} must be an integer of at least {minimum}")
    return value


def _number(value: object, label: str, *, minimum: float = 0.0) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < minimum
    ):
        raise ReleaseReportError(f"{label} must be a finite number of at least {minimum}")
    return float(value)


def _rate(value: object, label: str) -> float | None:
    if value is None:
        return None
    rate = _number(value, label)
    if rate > 1.0:
        raise ReleaseReportError(f"{label} must not exceed 1.0")
    return rate


def _expected_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _same_optional_rate(actual: float | None, expected: float | None) -> bool:
    if actual is None or expected is None:
        return actual is expected
    return math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12)


def _validated_metric(value: object, label: str, *, sentence: bool) -> dict[str, Any]:
    metric = _object(value, label)
    metric_fields = _SENTENCE_METRIC_FIELDS if sentence else _OCCURRENCE_METRIC_FIELDS
    count_fields = _SENTENCE_COUNT_FIELDS if sentence else _OCCURRENCE_COUNT_FIELDS
    _closed(metric, metric_fields, label)
    counts = _object(metric.get("counts"), f"{label}.counts")
    _closed(counts, count_fields, f"{label}.counts")
    validated_counts = {
        name: _integer(counts.get(name), f"{label}.counts.{name}") for name in count_fields
    }
    tp = validated_counts["tp"]
    fp = validated_counts["fp"]
    fn = validated_counts["fn"]
    expected_precision = _expected_rate(tp, tp + fp)
    expected_recall = _expected_rate(tp, tp + fn)
    expected_f1 = (
        None
        if expected_precision is None
        or expected_recall is None
        or expected_precision + expected_recall == 0
        else 2 * expected_precision * expected_recall / (expected_precision + expected_recall)
    )
    expected = {
        "precision": expected_precision,
        "recall": expected_recall,
        "f1": expected_f1,
    }
    if sentence:
        tn = validated_counts["tn"]
        expected["accuracy"] = _expected_rate(tp + tn, tp + fp + fn + tn)
    validated_rates = {name: _rate(metric.get(name), f"{label}.{name}") for name in expected}
    if any(
        not _same_optional_rate(validated_rates[name], expected_rate)
        for name, expected_rate in expected.items()
    ):
        raise ReleaseReportError(f"{label} rates do not match counts")
    return {"counts": validated_counts, **validated_rates}


def _validated_performance(value: object, label: str) -> dict[str, Any]:
    performance = _object(value, label)
    _closed(performance, _PERFORMANCE_FIELDS, label)
    workloads: dict[str, dict[str, int | float]] = {}
    for workload_id in ("short_chat", "maximum_input"):
        workload = _object(performance.get(workload_id), f"{label}.{workload_id}")
        _closed(workload, _WORKLOAD_FIELDS, f"{label}.{workload_id}")
        input_length = _integer(
            workload.get("input_length"),
            f"{label}.{workload_id}.input_length",
        )
        p50_ms = _number(workload.get("p50_ms"), f"{label}.{workload_id}.p50_ms")
        p95_ms = _number(workload.get("p95_ms"), f"{label}.{workload_id}.p95_ms")
        if p95_ms < p50_ms:
            raise ReleaseReportError(f"{label}.{workload_id} p95 must be at least p50")
        workloads[workload_id] = {
            "input_length": input_length,
            "p50_ms": p50_ms,
            "p95_ms": p95_ms,
        }
    return {
        **workloads,
        "engine_retained_memory_bytes": _integer(
            performance.get("engine_retained_memory_bytes"),
            f"{label}.engine_retained_memory_bytes",
            minimum=1,
        ),
    }


def _validated_artifact_audit(
    audit: Mapping[str, Any],
    *,
    release_commit: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    _closed(audit, _ARTIFACT_AUDIT_FIELDS, "artifact audit")
    if audit.get("schema_version") != 1:
        raise ReleaseReportError("artifact audit schema_version must equal 1")
    _timestamp(audit.get("generated_at"), "artifact audit generated_at")
    source = _object(audit.get("source"), "artifact audit source")
    _closed(source, _ARTIFACT_SOURCE_FIELDS, "artifact audit source")
    if source.get("release_commit") != release_commit:
        raise ReleaseReportError("artifact audit release commit does not match the release")
    tree = _string(source.get("git_tree"), "artifact audit source.git_tree")
    if _COMMIT_PATTERN.fullmatch(tree) is None:
        raise ReleaseReportError("artifact audit source.git_tree must be a full Git identifier")
    environment = _object(audit.get("environment"), "artifact audit environment")
    _closed(environment, _ARTIFACT_ENVIRONMENT_FIELDS, "artifact audit environment")
    if (
        environment.get("python_version") != "3.11.9"
        or environment.get("implementation") != "CPython"
    ):
        raise ReleaseReportError("artifact audit must run on CPython 3.11.9")
    _string(environment.get("platform"), "artifact audit environment.platform")
    package = _object(audit.get("package"), "artifact audit package")
    expected_package = {
        "name": "koguard",
        "version": "0.1.0",
        "requires_python": ">=3.11,<3.12",
        "license_expression": "MIT",
        "runtime_dependencies": [],
    }
    if package != expected_package:
        raise ReleaseReportError("artifact audit package metadata does not match 0.1.0")
    artifacts: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for raw_artifact in _array(audit.get("artifacts"), "artifact audit artifacts"):
        artifact = _object(raw_artifact, "artifact")
        kind = _string(artifact.get("kind"), "artifact.kind")
        if kind not in {"wheel", "sdist"} or kind in hashes:
            raise ReleaseReportError("artifact audit must contain one wheel and one sdist")
        _closed(artifact, _ARTIFACT_FIELDS[kind], f"{kind} artifact")
        digest = _sha256(artifact.get("sha256"), "artifact.sha256")
        filename = _string(artifact.get("filename"), "artifact.filename")
        if filename != _EXPECTED_FILENAMES[kind]:
            raise ReleaseReportError("artifact filename does not match the 0.1.0 contract")
        size = artifact.get("size_bytes")
        if type(size) is not int or size <= 0:
            raise ReleaseReportError("artifact.size_bytes must be a positive integer")
        _integer(artifact.get("member_count"), "artifact.member_count", minimum=1)
        detail_field = "bundled_notices" if kind == "wheel" else "release_evidence"
        details = _array(artifact.get(detail_field), f"artifact.{detail_field}")
        if not details or any(not isinstance(item, str) or not item for item in details):
            raise ReleaseReportError(f"artifact.{detail_field} must contain non-empty strings")
        hashes[kind] = digest
        artifacts.append({"kind": kind, "filename": filename, "size_bytes": size, "sha256": digest})
    if set(hashes) != {"wheel", "sdist"}:
        raise ReleaseReportError("artifact audit must contain one wheel and one sdist")
    artifacts.sort(key=lambda item: cast(str, item["kind"]))
    return dict(package), artifacts, hashes


def _validate_rights_manifest(rights: Mapping[str, Any]) -> None:
    try:
        validate_rights_manifest_payload(dict(rights))
    except ReleaseAuditError as exc:
        raise ReleaseReportError(str(exc)) from exc


def _ci_gate(ci: Mapping[str, Any], release_commit: str) -> bool:
    try:
        _closed(ci, _CI_FIELDS, "CI evidence")
        if (
            ci.get("schema_version") != 1
            or ci.get("provider") != "github-actions"
            or ci.get("repository") != "skgur07/Koguard"
            or ci.get("workflow") != "CI"
            or ci.get("head_sha") != release_commit
            or ci.get("event") not in {"push", "workflow_dispatch"}
            or ci.get("conclusion") != "success"
        ):
            return False
        run_id = _integer(ci.get("run_id"), "CI evidence.run_id", minimum=1)
        _integer(ci.get("run_attempt"), "CI evidence.run_attempt", minimum=1)
        run_url = _string(ci.get("run_url"), "CI evidence.run_url")
        if run_url != f"https://github.com/skgur07/Koguard/actions/runs/{run_id}":
            return False
        _timestamp(ci.get("verified_at"), "CI evidence.verified_at")
        raw_jobs = _array(ci.get("jobs"), "CI evidence.jobs")
        if len(raw_jobs) != len(_REQUIRED_JOBS):
            return False
        jobs_by_runner: dict[str, dict[str, Any]] = {}
        for raw_job in raw_jobs:
            job = _object(raw_job, "CI evidence job")
            _closed(job, _CI_JOB_FIELDS, "CI evidence job")
            runner = _string(job.get("runner"), "CI evidence job.runner")
            if runner in jobs_by_runner:
                return False
            _integer(job.get("job_id"), "CI evidence job.job_id", minimum=1)
            jobs_by_runner[runner] = job
        return all(
            runner in jobs_by_runner
            and jobs_by_runner[runner].get("name") == name
            and jobs_by_runner[runner].get("conclusion") == "success"
            for runner, name in _REQUIRED_JOBS
        )
    except ReleaseReportError:
        return False


def _public_contract_gate(contract: Mapping[str, Any]) -> bool:
    return set(contract) == set(_PUBLIC_CONTRACT_FIELDS) and all(
        contract.get(field) is True for field in _PUBLIC_CONTRACT_FIELDS
    )


def _validated_hidden_profile(
    value: object,
    *,
    case_count: int,
    positive_count: int,
    hard_negative_count: int,
) -> dict[str, Any]:
    profile = _object(value, "hidden profile")
    _closed(profile, _PROFILE_FIELDS, "hidden profile")
    profile_name = _string(profile.get("profile"), "hidden profile.profile")
    if profile_name not in _PROFILE_SOURCE_IDS:
        raise ReleaseReportError("hidden profile name is unsupported")
    if profile.get("source_profile_id") != _PROFILE_SOURCE_IDS[profile_name]:
        raise ReleaseReportError("hidden profile source_profile_id is inconsistent")
    settings = _object(profile.get("settings"), f"{profile_name}.settings")
    if settings != _profile_config_settings(cast(ProfileName, profile_name)):
        raise ReleaseReportError(f"hidden {profile_name} settings do not match the public profile")
    sentence = _validated_metric(
        profile.get("sentence_metrics"),
        f"{profile_name}.sentence_metrics",
        sentence=True,
    )
    sentence_counts = cast(dict[str, int], sentence["counts"])
    if sum(sentence_counts.values()) != case_count:
        raise ReleaseReportError(f"hidden {profile_name} sentence counts do not match corpus")
    if sentence_counts["tp"] + sentence_counts["fn"] != positive_count:
        raise ReleaseReportError(f"hidden {profile_name} positive counts do not match corpus")
    if sentence_counts["fp"] + sentence_counts["tn"] != hard_negative_count:
        raise ReleaseReportError(f"hidden {profile_name} negative counts do not match corpus")
    occurrence = _validated_metric(
        profile.get("occurrence_metrics"),
        f"{profile_name}.occurrence_metrics",
        sentence=False,
    )
    performance = _validated_performance(
        profile.get("performance"),
        f"{profile_name}.performance",
    )
    return {
        "profile": profile_name,
        "source_profile_id": profile["source_profile_id"],
        "settings": settings,
        "sentence_metrics": sentence,
        "occurrence_metrics": occurrence,
        "performance": performance,
    }


def _validated_hidden_report(hidden: Mapping[str, Any]) -> tuple[str, str]:
    _closed(hidden, _HIDDEN_FIELDS, "hidden evaluation report")
    if hidden.get("schema_version") != 1 or hidden.get("report_kind") != "hidden-evaluation":
        raise ReleaseReportError("hidden evaluation report header is unsupported")
    release_commit = _release_commit(hidden.get("release_commit"))

    evaluation = _object(hidden.get("evaluation"), "hidden evaluation")
    _closed(evaluation, _HIDDEN_EVALUATION_FIELDS, "hidden evaluation")
    for label in ("evaluation_id", "manifest_id"):
        identifier = _string(evaluation.get(label), f"hidden evaluation.{label}")
        if re.fullmatch(r"^[a-z0-9][a-z0-9._-]{0,127}$", identifier) is None:
            raise ReleaseReportError(f"hidden evaluation.{label} must be a stable identifier")
    _integer(evaluation.get("evaluation_version"), "evaluation_version", minimum=1)
    _integer(evaluation.get("manifest_version"), "manifest_version", minimum=1)
    if evaluation.get("normalization_version") != "nfkc-casefold-strip-pzc-repeat-v1":
        raise ReleaseReportError("hidden normalization version is unsupported")
    _sha256(evaluation.get("attestation_sha256"), "hidden attestation_sha256")
    if (
        evaluation.get("approval_count") != 2
        or evaluation.get("direct_leak_count") != 0
        or evaluation.get("normalized_leak_count") != 0
        or evaluation.get("gold_ready") is not True
    ):
        raise ReleaseReportError("hidden evaluation approval or leak evidence is not ready")
    evaluated_artifact = _object(
        evaluation.get("evaluated_artifact"),
        "hidden evaluated_artifact",
    )
    _closed(
        evaluated_artifact,
        _EVALUATED_ARTIFACT_FIELDS,
        "hidden evaluated_artifact",
    )
    if evaluated_artifact.get("kind") != "wheel":
        raise ReleaseReportError("hidden evaluation must use the audited wheel")
    evaluated_artifact_sha256 = _sha256(
        evaluated_artifact.get("sha256"),
        "hidden evaluated_artifact.sha256",
    )

    source = _object(hidden.get("source"), "hidden source")
    _closed(source, _HIDDEN_SOURCE_FIELDS, "hidden source")
    _sha256(
        source.get("protected_ablation_report_sha256"),
        "hidden source.protected_ablation_report_sha256",
    )
    _timestamp(source.get("measured_at"), "hidden source.measured_at")
    environment = _object(source.get("environment"), "hidden source.environment")
    _closed(environment, _HIDDEN_ENVIRONMENT_FIELDS, "hidden source.environment")
    if (
        environment.get("python_version") != "3.11.9"
        or environment.get("implementation") != "CPython"
    ):
        raise ReleaseReportError("hidden evaluation must run on CPython 3.11.9")
    for field in _HIDDEN_ENVIRONMENT_FIELDS:
        _string(environment.get(field), f"hidden source.environment.{field}")

    corpus = _object(source.get("corpus"), "hidden source.corpus")
    _closed(corpus, _HIDDEN_CORPUS_FIELDS, "hidden source.corpus")
    if (
        corpus.get("classification") != "independent-hidden-evaluation"
        or corpus.get("gold_ready") is not True
        or corpus.get("excluded_review_count") != 0
    ):
        raise ReleaseReportError("hidden corpus is not release-ready")
    _sha256(corpus.get("sha256"), "hidden source.corpus.sha256")
    case_count = _integer(corpus.get("case_count"), "hidden corpus.case_count", minimum=2)
    positive_count = _integer(
        corpus.get("positive_count"),
        "hidden corpus.positive_count",
        minimum=1,
    )
    hard_negative_count = _integer(
        corpus.get("hard_negative_count"),
        "hidden corpus.hard_negative_count",
        minimum=1,
    )
    if case_count != positive_count + hard_negative_count:
        raise ReleaseReportError("hidden corpus counts are inconsistent")

    raw_profiles = _array(hidden.get("profiles"), "hidden profiles")
    if len(raw_profiles) != 3:
        raise ReleaseReportError("hidden report must contain exactly three profiles")
    profiles = [
        _validated_hidden_profile(
            value,
            case_count=case_count,
            positive_count=positive_count,
            hard_negative_count=hard_negative_count,
        )
        for value in raw_profiles
    ]
    if [profile["profile"] for profile in profiles] != ["strict", "balanced", "aggressive"]:
        raise ReleaseReportError("hidden profiles must use canonical order")
    occurrence_totals = {
        cast(dict[str, int], profile["occurrence_metrics"]["counts"])["tp"]
        + cast(dict[str, int], profile["occurrence_metrics"]["counts"])["fn"]
        for profile in profiles
    }
    if len(occurrence_totals) != 1:
        raise ReleaseReportError("hidden occurrence gold totals are inconsistent")
    workload_lengths = {
        (
            cast(dict[str, Any], profile["performance"])["short_chat"]["input_length"],
            cast(dict[str, Any], profile["performance"])["maximum_input"]["input_length"],
        )
        for profile in profiles
    }
    if len(workload_lengths) != 1:
        raise ReleaseReportError("hidden performance workload lengths are inconsistent")

    by_name = {cast(str, profile["profile"]): profile for profile in profiles}
    strict_sentence = cast(dict[str, int], by_name["strict"]["sentence_metrics"]["counts"])
    balanced_sentence = cast(
        dict[str, int],
        by_name["balanced"]["sentence_metrics"]["counts"],
    )
    strict_occurrence = cast(
        dict[str, int],
        by_name["strict"]["occurrence_metrics"]["counts"],
    )
    balanced_occurrence = cast(
        dict[str, int],
        by_name["balanced"]["occurrence_metrics"]["counts"],
    )
    expected_evidence = {
        "sentence_tp_delta_vs_strict": balanced_sentence["tp"] - strict_sentence["tp"],
        "sentence_fp_delta_vs_strict": balanced_sentence["fp"] - strict_sentence["fp"],
        "occurrence_tp_delta_vs_strict": balanced_occurrence["tp"] - strict_occurrence["tp"],
        "occurrence_fp_delta_vs_strict": balanced_occurrence["fp"] - strict_occurrence["fp"],
    }
    evidence = _object(hidden.get("balanced_evidence"), "hidden balanced_evidence")
    _closed(evidence, _BALANCED_EVIDENCE_FIELDS, "hidden balanced_evidence")
    if any(type(evidence.get(key)) is not int for key in _BALANCED_EVIDENCE_FIELDS):
        raise ReleaseReportError("hidden balanced evidence deltas must be integers")
    if evidence != expected_evidence:
        raise ReleaseReportError("hidden balanced evidence does not match profile counts")

    gates = _object(hidden.get("balanced_gates"), "hidden balanced_gates")
    _closed(gates, _BALANCED_GATE_FIELDS, "hidden balanced_gates")
    balanced_performance = cast(dict[str, Any], by_name["balanced"]["performance"])
    expected_gate_values = {
        "normal_sentence_fp_rate": balanced_sentence["fp"] / hard_negative_count,
        "normal_sentence_fp_rate_limit": 0.005,
        "short_chat_p95_ms": balanced_performance["short_chat"]["p95_ms"],
        "short_chat_p95_ms_limit": 1.0,
        "maximum_input_p95_ms": balanced_performance["maximum_input"]["p95_ms"],
        "maximum_input_p95_ms_limit": 15.0,
    }
    validated_gate_values = {
        key: _number(gates.get(key), f"hidden balanced_gates.{key}") for key in expected_gate_values
    }
    if any(
        not math.isclose(validated_gate_values[key], expected, rel_tol=1e-12, abs_tol=1e-12)
        for key, expected in expected_gate_values.items()
    ):
        raise ReleaseReportError("hidden balanced gates do not match profile evidence")
    expected_passed = (
        expected_gate_values["normal_sentence_fp_rate"]
        <= expected_gate_values["normal_sentence_fp_rate_limit"]
        and expected_gate_values["short_chat_p95_ms"]
        <= expected_gate_values["short_chat_p95_ms_limit"]
        and expected_gate_values["maximum_input_p95_ms"]
        <= expected_gate_values["maximum_input_p95_ms_limit"]
        and expected_evidence["sentence_tp_delta_vs_strict"] > 0
        and expected_evidence["sentence_fp_delta_vs_strict"] == 0
        and expected_evidence["occurrence_tp_delta_vs_strict"] > 0
        and expected_evidence["occurrence_fp_delta_vs_strict"] == 0
    )
    if gates.get("passed") is not expected_passed or not expected_passed:
        raise ReleaseReportError("hidden balanced gates have not passed")

    raw_slices = _array(hidden.get("balanced_slice_metrics"), "hidden balanced_slice_metrics")
    if not raw_slices:
        raise ReleaseReportError("hidden balanced slice metrics must not be empty")
    seen_slices: set[str] = set()
    for raw_slice in raw_slices:
        slice_metric = _object(raw_slice, "hidden balanced slice metric")
        _closed(slice_metric, _SLICE_FIELDS, "hidden balanced slice metric")
        slice_name = _string(slice_metric.get("slice"), "hidden balanced slice metric.slice")
        if slice_name in seen_slices:
            raise ReleaseReportError(f"duplicate hidden slice: {slice_name}")
        seen_slices.add(slice_name)
        _integer(
            slice_metric.get("case_count"),
            "hidden balanced slice metric.case_count",
            minimum=1,
        )
        _validated_metric(
            slice_metric.get("sentence_metrics"),
            f"hidden slice {slice_name}.sentence_metrics",
            sentence=True,
        )
        _validated_metric(
            slice_metric.get("occurrence_metrics"),
            f"hidden slice {slice_name}.occurrence_metrics",
            sentence=False,
        )

    limitations = _array(hidden.get("limitations"), "hidden limitations")
    if not limitations or any(not isinstance(item, str) or not item for item in limitations):
        raise ReleaseReportError("hidden limitations must contain non-empty strings")
    return release_commit, evaluated_artifact_sha256


def _hidden_gate(
    hidden: Mapping[str, Any] | None,
    release_commit: str,
    artifact_hashes: Mapping[str, str],
    blockers: list[str],
) -> bool:
    if hidden is None:
        blockers.append("hidden-evaluation-missing")
        return False
    if hidden.get("release_commit") != release_commit:
        blockers.append("hidden-release-commit-mismatch")
        return False
    try:
        validated_commit, evaluated_artifact_sha256 = _validated_hidden_report(hidden)
    except ReleaseReportError:
        blockers.append("hidden-evaluation-not-ready")
        return False
    if validated_commit != release_commit:
        blockers.append("hidden-release-commit-mismatch")
        return False
    if evaluated_artifact_sha256 != artifact_hashes["wheel"]:
        blockers.append("hidden-artifact-mismatch")
        return False
    return True


def _testpypi_gate(
    evidence: Mapping[str, Any] | None,
    artifact_hashes: Mapping[str, str],
    blockers: list[str],
) -> bool:
    if evidence is None:
        blockers.append("testpypi-evidence-missing")
        return False
    if set(evidence) != _TESTPYPI_FIELDS:
        blockers.append("testpypi-evidence-incomplete")
        return False
    package = evidence.get("package")
    artifacts = evidence.get("artifacts")
    structurally_ready = (
        evidence.get("schema_version") == 1
        and evidence.get("index_url") == "https://test.pypi.org/simple/"
        and isinstance(evidence.get("project_url"), str)
        and cast(str, evidence["project_url"]) == "https://test.pypi.org/project/koguard/0.1.0/"
        and package == {"name": "koguard", "version": "0.1.0"}
        and evidence.get("python_version") == "3.11.9"
        and evidence.get("metadata_verified") is True
        and isinstance(artifacts, list)
        and len(artifacts) == 2
    )
    if not structurally_ready:
        blockers.append("testpypi-evidence-incomplete")
        return False
    try:
        _timestamp(evidence.get("tested_at"), "testpypi_evidence.tested_at")
    except ReleaseReportError:
        blockers.append("testpypi-evidence-incomplete")
        return False
    observed: dict[str, str] = {}
    for raw_artifact in cast(list[object], artifacts):
        artifact = _object(raw_artifact, "TestPyPI artifact")
        if set(artifact) != _TESTPYPI_ARTIFACT_FIELDS:
            blockers.append("testpypi-evidence-incomplete")
            return False
        kind = artifact.get("kind")
        digest = artifact.get("sha256")
        if (
            kind not in {"wheel", "sdist"}
            or not isinstance(digest, str)
            or _SHA256_PATTERN.fullmatch(digest) is None
            or artifact.get("smoke_passed") is not True
        ):
            blockers.append("testpypi-evidence-incomplete")
            return False
        if kind in observed:
            blockers.append("testpypi-evidence-incomplete")
            return False
        observed[cast(str, kind)] = digest
    if observed != artifact_hashes:
        blockers.append("testpypi-artifact-mismatch")
        return False
    return True


def build_release_report(
    artifact_audit: Mapping[str, Any],
    rights_manifest: Mapping[str, Any],
    *,
    release_commit: str,
    ci_evidence: Mapping[str, Any],
    public_contract: Mapping[str, Any],
    hidden_evaluation: Mapping[str, Any] | None = None,
    testpypi_evidence: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a non-publishing release decision from supplied evidence."""

    commit = _release_commit(release_commit)
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ReleaseReportError("generated_at must include timezone information")
    package, artifacts, artifact_hashes = _validated_artifact_audit(
        artifact_audit,
        release_commit=commit,
    )
    _validate_rights_manifest(rights_manifest)
    blockers: list[str] = []
    ci_passed = _ci_gate(ci_evidence, commit)
    if not ci_passed:
        blockers.append("ci-evidence-not-ready")
    public_contract_passed = _public_contract_gate(public_contract)
    if not public_contract_passed:
        blockers.append("public-contract-not-ready")
    hidden_passed = _hidden_gate(hidden_evaluation, commit, artifact_hashes, blockers)
    testpypi_passed = _testpypi_gate(testpypi_evidence, artifact_hashes, blockers)
    gates = {
        "artifacts": True,
        "rights": True,
        "ci": ci_passed,
        "public_contract": public_contract_passed,
        "hidden_evaluation": hidden_passed,
        "testpypi": testpypi_passed,
    }
    return {
        "schema_version": 1,
        "generated_at": timestamp.astimezone(UTC).isoformat(),
        "release": {"name": "koguard", "version": "0.1.0", "commit": commit},
        "evidence": {
            "artifact_audit_sha256": _canonical_sha256(artifact_audit),
            "rights_manifest_sha256": _canonical_sha256(rights_manifest),
            "ci_evidence_sha256": _canonical_sha256(ci_evidence),
            "hidden_evaluation_sha256": (
                _canonical_sha256(hidden_evaluation) if hidden_evaluation is not None else None
            ),
            "testpypi_evidence_sha256": (
                _canonical_sha256(testpypi_evidence) if testpypi_evidence is not None else None
            ),
            "ci_run_url": _string(ci_evidence.get("run_url"), "ci_evidence.run_url"),
        },
        "package": package,
        "artifacts": artifacts,
        "gates": gates,
        "blockers": blockers,
        "decision": "ready-for-maintainer-approval" if all(gates.values()) else "blocked",
        "publication": {
            "maintainer_approval_required": True,
            "main_promoted": False,
            "pypi_published": False,
        },
    }


def _load_optional(path: Path | None, label: str) -> dict[str, Any] | None:
    if path is None:
        return None
    return _load_object(path, label)


def _load_object(path: Path, label: str) -> dict[str, Any]:
    try:
        return _object(json.loads(path.read_text(encoding="utf-8")), label)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseReportError(f"failed to read {label}") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-audit", type=Path, required=True)
    parser.add_argument(
        "--rights-manifest", type=Path, default=Path("release/rights-manifest.v1.json")
    )
    parser.add_argument("--release-commit", required=True)
    parser.add_argument("--ci-run-url", required=True)
    parser.add_argument("--hidden-evaluation", type=Path)
    parser.add_argument("--testpypi-evidence", type=Path)
    parser.add_argument("--public-contract-reviewed", action="store_true")
    parser.add_argument("--private-vulnerability-reporting-enabled", action="store_true")
    parser.add_argument("--output", type=Path, default=Path("release-report.json"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write a draft or ready-for-approval PF-014 release report."""

    arguments = _parser().parse_args(argv)
    try:
        reviewed = arguments.public_contract_reviewed
        ci_evidence = fetch_github_actions_evidence(
            arguments.ci_run_url,
            expected_commit=arguments.release_commit,
        )
        report = build_release_report(
            _load_object(arguments.artifact_audit, "artifact audit"),
            _load_object(arguments.rights_manifest, "rights manifest"),
            release_commit=arguments.release_commit,
            ci_evidence=ci_evidence,
            public_contract={
                "public_api_frozen": reviewed,
                "readme_claims_reviewed": reviewed,
                "limitations_documented": reviewed,
                "core_ai_scope_separated": reviewed,
                "private_vulnerability_reporting_enabled": (
                    arguments.private_vulnerability_reporting_enabled
                ),
            },
            hidden_evaluation=_load_optional(arguments.hidden_evaluation, "hidden evaluation"),
            testpypi_evidence=_load_optional(arguments.testpypi_evidence, "TestPyPI evidence"),
        )
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"release decision={report['decision']}; "
            f"blockers={','.join(cast(list[str], report['blockers'])) or 'none'}"
        )
    except (GitHubActionsEvidenceError, ReleaseReportError) as exc:
        print(f"release report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
