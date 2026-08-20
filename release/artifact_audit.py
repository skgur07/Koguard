"""Audit Koguard wheel and sdist contents before publication."""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
import tarfile
import zipfile
from collections.abc import Sequence
from datetime import UTC, date, datetime
from email import policy
from email.message import Message
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

ARTIFACT_AUDIT_SCHEMA_PATH = Path(__file__).with_name("artifact-audit.schema.json")
RIGHTS_MANIFEST_SCHEMA_PATH = Path(__file__).with_name("rights-manifest.schema.json")

_PACKAGE_NAME = "koguard"
_PACKAGE_VERSION = "0.1.0"
_REQUIRES_PYTHON = ">=3.11,<3.12"
_LICENSE_EXPRESSION = "MIT"
_MAX_WHEEL_BYTES = 256 * 1024
_MAX_SDIST_BYTES = 2 * 1024 * 1024
_GIT_OID_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_RIGHTS_FIELDS = frozenset(
    {"schema_version", "reviewed_at", "project_license", "artifact_policy", "sources"}
)
_RIGHTS_SOURCE_FIELDS = frozenset(
    {
        "source_id",
        "reference",
        "revision",
        "declared_license",
        "rights_status",
        "allowed_scope",
        "payload_in_artifacts",
        "runtime_dependency",
        "evidence",
    }
)
_FORBIDDEN_SUFFIXES = frozenset(
    {
        ".bin",
        ".csv",
        ".joblib",
        ".npy",
        ".npz",
        ".onnx",
        ".parquet",
        ".pickle",
        ".pkl",
        ".pt",
        ".safetensors",
    }
)
_FORBIDDEN_SDIST_PARTS = (
    "/evaluation/annotation-work/",
    "/evaluation/corpus/tuning/",
    "/evaluation/hidden/",
    "/evaluation/private/",
    "/evaluation/protected/",
    "/evaluation/quarantine/",
)


class ReleaseAuditError(ValueError):
    """Raised when a distribution violates the public release contract."""


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_source_identity(repo_root: Path) -> tuple[str, str]:
    """Return the clean checkout's commit and Git tree identifiers."""

    resolved_root = repo_root.resolve()
    for arguments, label in (
        (("diff", "--quiet"), "tracked worktree"),
        (("diff", "--cached", "--quiet"), "staged worktree"),
    ):
        completed = subprocess.run(
            ("git", "-C", str(resolved_root), *arguments),
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise ReleaseAuditError(f"{label} must be clean before release artifact audit")

    identifiers: list[str] = []
    for revision in ("HEAD", "HEAD^{tree}"):
        completed = subprocess.run(
            ("git", "-C", str(resolved_root), "rev-parse", "--verify", revision),
            check=False,
            capture_output=True,
            text=True,
        )
        identifier = completed.stdout.strip()
        if completed.returncode != 0 or _GIT_OID_PATTERN.fullmatch(identifier) is None:
            raise ReleaseAuditError(f"failed to resolve Git identity: {revision}")
        identifiers.append(identifier)
    return identifiers[0], identifiers[1]


def _require_one(paths: Sequence[Path], label: str) -> Path:
    if len(paths) != 1:
        raise ReleaseAuditError(f"expected exactly one {label}, found {len(paths)}")
    return paths[0]


def discover_distributions(dist_dir: Path) -> tuple[Path, Path]:
    """Return the one wheel and one source distribution in a build directory."""

    wheel = _require_one(sorted(dist_dir.glob("*.whl")), "wheel")
    sdist = _require_one(sorted(dist_dir.glob("*.tar.gz")), "sdist")
    return wheel, sdist


def _metadata_payload(message: Message) -> dict[str, object]:
    requirements = message.get_all("Requires-Dist", [])
    payload: dict[str, object] = {
        "name": message.get("Name"),
        "version": message.get("Version"),
        "requires_python": message.get("Requires-Python"),
        "license_expression": message.get("License-Expression"),
        "runtime_dependencies": requirements,
    }
    expected = {
        "name": _PACKAGE_NAME,
        "version": _PACKAGE_VERSION,
        "requires_python": _REQUIRES_PYTHON,
        "license_expression": _LICENSE_EXPRESSION,
        "runtime_dependencies": [],
    }
    actual_requires_python = payload["requires_python"]
    if not isinstance(actual_requires_python, str) or _specifier_parts(
        actual_requires_python
    ) != _specifier_parts(_REQUIRES_PYTHON):
        raise ReleaseAuditError(f"distribution metadata mismatch: {payload!r}")
    payload["requires_python"] = _REQUIRES_PYTHON
    if payload != expected:
        raise ReleaseAuditError(f"distribution metadata mismatch: {payload!r}")
    return payload


def _specifier_parts(value: str) -> frozenset[str]:
    """Normalize the order and surrounding whitespace of a specifier list."""

    return frozenset(part.strip() for part in value.split(",") if part.strip())


def _parse_metadata(content: bytes) -> dict[str, object]:
    message = BytesParser(policy=policy.default).parsebytes(content)
    return _metadata_payload(message)


def _require_members(names: set[str], required: Sequence[str], label: str) -> None:
    missing = [member for member in required if member not in names]
    if missing:
        raise ReleaseAuditError(f"{label} is missing required members: {missing}")


def _validate_archive_names(names: Sequence[str], label: str) -> None:
    if len(names) != len(set(names)):
        raise ReleaseAuditError(f"{label} contains duplicate member names")
    for name in names:
        path = PurePosixPath(name)
        if not path.parts or path.is_absolute() or "\\" in name:
            raise ReleaseAuditError(f"unsafe {label} member name: {name}")
        if any(part in {"", ".", ".."} for part in path.parts):
            raise ReleaseAuditError(f"unsafe {label} member name: {name}")


def _audit_wheel(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        member_names = archive.namelist()
        _validate_archive_names(member_names, "wheel")
        names = set(member_names)
        metadata_names = [name for name in names if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise ReleaseAuditError("wheel must contain exactly one METADATA file")
        metadata = _parse_metadata(archive.read(metadata_names[0]))
        dist_info = metadata_names[0].removesuffix("METADATA")
        _require_members(
            names,
            (
                "koguard/data/NOTICE.md",
                "koguard/data/KORCEN-MIT.txt",
                "koguard/data/CURSE-DETECTION-DATA-MIT.txt",
                f"{dist_info}licenses/LICENSE",
                f"{dist_info}RECORD",
            ),
            "wheel",
        )
        allowed_roots = {"koguard", PurePosixPath(metadata_names[0]).parts[0]}
        for name in sorted(names):
            pure_path = PurePosixPath(name)
            if pure_path.suffix.lower() in _FORBIDDEN_SUFFIXES:
                raise ReleaseAuditError(f"forbidden wheel member: {name}")
            if pure_path.parts[0] not in allowed_roots:
                raise ReleaseAuditError(f"unexpected wheel member root: {name}")
        details = {
            "member_count": len(names),
            "bundled_notices": [
                "koguard/data/NOTICE.md",
                "koguard/data/KORCEN-MIT.txt",
                "koguard/data/CURSE-DETECTION-DATA-MIT.txt",
                f"{dist_info}licenses/LICENSE",
            ],
        }
    return metadata, details


def _audit_sdist(path: Path) -> tuple[dict[str, object], dict[str, object]]:
    with tarfile.open(path, "r:gz") as archive:
        members = archive.getmembers()
        member_names = [member.name for member in members]
        _validate_archive_names(member_names, "sdist")
        unsupported = [member.name for member in members if not (member.isfile() or member.isdir())]
        if unsupported:
            raise ReleaseAuditError(f"sdist contains unsupported member types: {unsupported}")
        names = {member.name for member in members if member.isfile()}
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise ReleaseAuditError("sdist must have exactly one top-level directory")
        root = next(iter(roots))
        prefix = f"{root}/"
        required_relative = (
            "LICENSE",
            "README.md",
            "CHANGELOG.md",
            "SECURITY.md",
            "CONTRIBUTING.md",
            "pyproject.toml",
            "PKG-INFO",
            "src/koguard/data/NOTICE.md",
            "src/koguard/data/KORCEN-MIT.txt",
            "src/koguard/data/CURSE-DETECTION-DATA-MIT.txt",
            "docs/release-hardening.md",
            "docs/pf014-release-readiness.md",
            "evaluation/hidden_evaluation_report.py",
            "evaluation/hidden-evaluation-attestation.schema.json",
            "evaluation/hidden-evaluation-report.schema.json",
            "release/release_report.py",
            "release/release-report.schema.json",
            "release/artifact-audit.schema.json",
            "release/ci-evidence.schema.json",
            "release/github_actions_evidence.py",
            "release/reproducibility-report.schema.json",
            "release/rights-manifest.schema.json",
            "release/rights-manifest.v1.json",
            "release/testpypi-evidence.schema.json",
            "release/verify_reproducible_artifacts.py",
        )
        _require_members(
            names,
            tuple(prefix + relative for relative in required_relative),
            "sdist",
        )
        metadata_member = archive.extractfile(prefix + "PKG-INFO")
        if metadata_member is None:
            raise ReleaseAuditError("sdist PKG-INFO is unreadable")
        metadata = _parse_metadata(metadata_member.read())
        for name in sorted(names):
            normalized_name = "/" + name.lower()
            if any(part in normalized_name for part in _FORBIDDEN_SDIST_PARTS):
                raise ReleaseAuditError(f"forbidden sdist member: {name}")
            if PurePosixPath(name).name.lower() == "dataset.txt":
                raise ReleaseAuditError(f"forbidden sdist member: {name}")
            if PurePosixPath(name).suffix.lower() in _FORBIDDEN_SUFFIXES:
                raise ReleaseAuditError(f"forbidden sdist member: {name}")
        details = {
            "member_count": len(names),
            "release_evidence": [prefix + relative for relative in required_relative],
        }
    return metadata, details


def audit_distributions(
    dist_dir: Path,
    *,
    release_commit: str,
    source_tree: str,
) -> dict[str, Any]:
    """Validate both distributions and return hashes, sizes, and package metadata."""

    if _GIT_OID_PATTERN.fullmatch(release_commit) is None:
        raise ReleaseAuditError("release_commit must be a full lowercase Git SHA")
    if _GIT_OID_PATTERN.fullmatch(source_tree) is None:
        raise ReleaseAuditError("source_tree must be a full lowercase Git tree identifier")
    wheel, sdist = discover_distributions(dist_dir)
    if wheel.stat().st_size > _MAX_WHEEL_BYTES:
        raise ReleaseAuditError(f"wheel exceeds {_MAX_WHEEL_BYTES} bytes")
    if sdist.stat().st_size > _MAX_SDIST_BYTES:
        raise ReleaseAuditError(f"sdist exceeds {_MAX_SDIST_BYTES} bytes")
    wheel_metadata, wheel_details = _audit_wheel(wheel)
    sdist_metadata, sdist_details = _audit_sdist(sdist)
    if wheel_metadata != sdist_metadata:
        raise ReleaseAuditError("wheel and sdist metadata differ")
    return {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "release_commit": release_commit,
            "git_tree": source_tree,
        },
        "environment": {
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
        },
        "package": wheel_metadata,
        "artifacts": [
            {
                "kind": "wheel",
                "filename": wheel.name,
                "size_bytes": wheel.stat().st_size,
                "sha256": _hash_file(wheel),
                **wheel_details,
            },
            {
                "kind": "sdist",
                "filename": sdist.name,
                "size_bytes": sdist.stat().st_size,
                "sha256": _hash_file(sdist),
                **sdist_details,
            },
        ],
    }


def validate_rights_manifest_payload(payload: object) -> dict[str, object]:
    """Validate the closed rights manifest and block unapproved public payload."""

    if not isinstance(payload, dict):
        raise ReleaseAuditError("rights manifest must be an object")
    if set(payload) != _RIGHTS_FIELDS:
        raise ReleaseAuditError("rights manifest fields do not match the closed contract")
    if payload.get("schema_version") != 1:
        raise ReleaseAuditError("rights manifest must use schema_version 1")
    if payload.get("project_license") != _LICENSE_EXPRESSION:
        raise ReleaseAuditError("project license is not approved for release")
    reviewed_at = payload.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        raise ReleaseAuditError("rights manifest reviewed_at must be an ISO date")
    try:
        date.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise ReleaseAuditError("rights manifest reviewed_at must be an ISO date") from exc
    if not isinstance(payload.get("artifact_policy"), str) or not payload["artifact_policy"]:
        raise ReleaseAuditError("rights manifest artifact_policy must be non-empty")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ReleaseAuditError("rights manifest must contain sources")
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            raise ReleaseAuditError("rights manifest sources must be objects")
        if set(source) != _RIGHTS_SOURCE_FIELDS:
            raise ReleaseAuditError("rights source fields do not match the closed contract")
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or _SOURCE_ID_PATTERN.fullmatch(source_id) is None:
            raise ReleaseAuditError("rights source_id must be a stable identifier")
        if source_id in source_ids:
            raise ReleaseAuditError(f"duplicate rights source: {source_id}")
        source_ids.add(source_id)
        for field in ("reference", "revision", "rights_status", "allowed_scope", "evidence"):
            if not isinstance(source.get(field), str) or not source[field]:
                raise ReleaseAuditError(f"rights source {field} must be non-empty: {source_id}")
        declared_license = source.get("declared_license")
        if declared_license is not None and (
            not isinstance(declared_license, str) or not declared_license
        ):
            raise ReleaseAuditError(f"declared_license must be a string or null: {source_id}")
        if type(source.get("payload_in_artifacts")) is not bool:
            raise ReleaseAuditError(f"payload_in_artifacts must be boolean: {source_id}")
        if source.get("runtime_dependency") is not False:
            raise ReleaseAuditError(f"runtime dependency is not allowed: {source_id}")
        if source.get("payload_in_artifacts") is True and source.get("rights_status") != "approved":
            raise ReleaseAuditError(f"unapproved public payload: {source_id}")
    return payload


def validate_rights_manifest(path: Path) -> dict[str, object]:
    """Load and validate the closed release rights manifest."""

    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseAuditError(f"failed to load rights manifest: {path}") from exc
    return validate_rights_manifest_payload(payload)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument(
        "--rights-manifest",
        type=Path,
        default=Path("release/rights-manifest.v1.json"),
    )
    parser.add_argument("--output", type=Path, default=Path("release-audit.json"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Validate release rights and artifacts, then write a machine-readable report."""

    arguments = _parser().parse_args(argv)
    validate_rights_manifest(arguments.rights_manifest)
    release_commit, source_tree = _git_source_identity(arguments.repo_root)
    report = audit_distributions(
        arguments.dist_dir,
        release_commit=release_commit,
        source_tree=source_tree,
    )
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    arguments.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
