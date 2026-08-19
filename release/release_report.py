"""Combine PF-014 evidence into a deterministic release decision report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

RELEASE_REPORT_SCHEMA_PATH = Path(__file__).with_name("release-report.schema.json")
TESTPYPI_EVIDENCE_SCHEMA_PATH = Path(__file__).with_name("testpypi-evidence.schema.json")
_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_PLATFORMS = frozenset({"ubuntu-latest", "windows-latest", "macos-latest"})
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


def _validated_artifact_audit(
    audit: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, str]]:
    if audit.get("schema_version") != 1:
        raise ReleaseReportError("artifact audit schema_version must equal 1")
    environment = _object(audit.get("environment"), "artifact audit environment")
    if (
        environment.get("python_version") != "3.11.9"
        or environment.get("implementation") != "CPython"
    ):
        raise ReleaseReportError("artifact audit must run on CPython 3.11.9")
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
        digest = _sha256(artifact.get("sha256"), "artifact.sha256")
        filename = _string(artifact.get("filename"), "artifact.filename")
        if filename != _EXPECTED_FILENAMES[kind]:
            raise ReleaseReportError("artifact filename does not match the 0.1.0 contract")
        size = artifact.get("size_bytes")
        if type(size) is not int or size <= 0:
            raise ReleaseReportError("artifact.size_bytes must be a positive integer")
        hashes[kind] = digest
        artifacts.append({"kind": kind, "filename": filename, "size_bytes": size, "sha256": digest})
    if set(hashes) != {"wheel", "sdist"}:
        raise ReleaseReportError("artifact audit must contain one wheel and one sdist")
    artifacts.sort(key=lambda item: cast(str, item["kind"]))
    return dict(package), artifacts, hashes


def _validate_rights_manifest(rights: Mapping[str, Any]) -> None:
    if rights.get("schema_version") != 1 or rights.get("project_license") != "MIT":
        raise ReleaseReportError("rights manifest is not approved for MIT release")
    sources = _array(rights.get("sources"), "rights manifest sources")
    if not sources:
        raise ReleaseReportError("rights manifest sources must not be empty")
    for raw_source in sources:
        source = _object(raw_source, "rights source")
        if source.get("runtime_dependency") is not False:
            raise ReleaseReportError("runtime dependency is not allowed in the release manifest")
        if source.get("payload_in_artifacts") is True and source.get("rights_status") != "approved":
            raise ReleaseReportError("unapproved public payload is present in rights manifest")


def _ci_gate(ci: Mapping[str, Any], release_commit: str) -> bool:
    platforms = ci.get("platforms")
    valid_platforms = (
        isinstance(platforms, list)
        and all(isinstance(platform, str) for platform in platforms)
        and set(platforms) == _REQUIRED_PLATFORMS
    )
    return (
        ci.get("status") == "passed"
        and ci.get("head_sha") == release_commit
        and isinstance(ci.get("run_url"), str)
        and cast(str, ci["run_url"]).startswith("https://github.com/skgur07/Koguard/actions/runs/")
        and valid_platforms
    )


def _public_contract_gate(contract: Mapping[str, Any]) -> bool:
    return all(contract.get(field) is True for field in _PUBLIC_CONTRACT_FIELDS)


def _hidden_gate(
    hidden: Mapping[str, Any] | None,
    release_commit: str,
    blockers: list[str],
) -> bool:
    if hidden is None:
        blockers.append("hidden-evaluation-missing")
        return False
    if hidden.get("release_commit") != release_commit:
        blockers.append("hidden-release-commit-mismatch")
        return False
    evaluation = _object(hidden.get("evaluation"), "hidden evaluation")
    source = _object(hidden.get("source"), "hidden source")
    corpus = _object(source.get("corpus"), "hidden source.corpus")
    gates = _object(hidden.get("balanced_gates"), "hidden balanced_gates")
    if (
        hidden.get("schema_version") != 1
        or hidden.get("report_kind") != "hidden-evaluation"
        or evaluation.get("gold_ready") is not True
        or evaluation.get("approval_count") != 2
        or evaluation.get("direct_leak_count") != 0
        or evaluation.get("normalized_leak_count") != 0
        or not isinstance(evaluation.get("attestation_sha256"), str)
        or _SHA256_PATTERN.fullmatch(cast(str, evaluation["attestation_sha256"])) is None
        or not isinstance(source.get("protected_ablation_report_sha256"), str)
        or _SHA256_PATTERN.fullmatch(cast(str, source["protected_ablation_report_sha256"])) is None
        or corpus.get("classification") != "independent-hidden-evaluation"
        or corpus.get("gold_ready") is not True
        or corpus.get("excluded_review_count") != 0
        or gates.get("passed") is not True
    ):
        blockers.append("hidden-evaluation-not-ready")
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
    package, artifacts, artifact_hashes = _validated_artifact_audit(artifact_audit)
    _validate_rights_manifest(rights_manifest)
    blockers: list[str] = []
    ci_passed = _ci_gate(ci_evidence, commit)
    if not ci_passed:
        blockers.append("ci-evidence-not-ready")
    public_contract_passed = _public_contract_gate(public_contract)
    if not public_contract_passed:
        blockers.append("public-contract-not-ready")
    hidden_passed = _hidden_gate(hidden_evaluation, commit, blockers)
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
    parser.add_argument("--ci-head-sha", required=True)
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
        report = build_release_report(
            _load_object(arguments.artifact_audit, "artifact audit"),
            _load_object(arguments.rights_manifest, "rights manifest"),
            release_commit=arguments.release_commit,
            ci_evidence={
                "status": "passed",
                "head_sha": arguments.ci_head_sha,
                "run_url": arguments.ci_run_url,
                "platforms": sorted(_REQUIRED_PLATFORMS),
            },
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
    except ReleaseReportError as exc:
        print(f"release report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
