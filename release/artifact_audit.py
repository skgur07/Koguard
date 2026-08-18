"""Audit Koguard wheel and sdist contents before publication."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tarfile
import zipfile
from collections.abc import Sequence
from datetime import UTC, datetime
from email import policy
from email.message import Message
from email.parser import BytesParser
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import Any

_PACKAGE_NAME = "koguard"
_PACKAGE_VERSION = "0.1.0"
_REQUIRES_PYTHON = ">=3.11,<3.12"
_LICENSE_EXPRESSION = "MIT"
_MAX_WHEEL_BYTES = 256 * 1024
_MAX_SDIST_BYTES = 2 * 1024 * 1024
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
            "release/rights-manifest.v1.json",
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


def audit_distributions(dist_dir: Path) -> dict[str, Any]:
    """Validate both distributions and return hashes, sizes, and package metadata."""

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


def validate_rights_manifest(path: Path) -> dict[str, object]:
    """Block public payload whose rights status is not approved."""

    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReleaseAuditError(f"failed to load rights manifest: {path}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise ReleaseAuditError("rights manifest must use schema_version 1")
    if payload.get("project_license") != _LICENSE_EXPRESSION:
        raise ReleaseAuditError("project license is not approved for release")
    sources = payload.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ReleaseAuditError("rights manifest must contain sources")
    for source in sources:
        if not isinstance(source, dict):
            raise ReleaseAuditError("rights manifest sources must be objects")
        if source.get("runtime_dependency") is not False:
            raise ReleaseAuditError(f"runtime dependency is not allowed: {source.get('source_id')}")
        if source.get("payload_in_artifacts") is True and source.get("rights_status") != "approved":
            raise ReleaseAuditError(f"unapproved public payload: {source.get('source_id')}")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
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
    report = audit_distributions(arguments.dist_dir)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    arguments.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
