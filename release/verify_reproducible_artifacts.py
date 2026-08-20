"""Verify that three OS candidates contain byte-identical release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

REPRODUCIBILITY_REPORT_SCHEMA_PATH = Path(__file__).with_name("reproducibility-report.schema.json")
_BUILDERS = ("Linux", "Windows", "macOS")
_EXPECTED_FILENAMES = {
    "wheel": "koguard-0.1.0-py3-none-any.whl",
    "sdist": "koguard-0.1.0.tar.gz",
}
_GIT_OID_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ReproducibilityError(ValueError):
    """Raised when candidate artifacts are incomplete or not reproducible."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReproducibilityError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_audit(path: Path) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReproducibilityError(f"failed to load artifact audit: {path}") from exc
    return _object(payload, "artifact audit")


def _validated_candidate(root: Path, builder: str) -> dict[str, Any]:
    candidate = root / f"koguard-0.1.0-candidate-{builder}-python311"
    if not candidate.is_dir():
        raise ReproducibilityError(f"missing candidate directory: {candidate.name}")
    audit_path = candidate / f"release-audit-{builder}.json"
    audit = _load_audit(audit_path)
    if audit.get("schema_version") != 1:
        raise ReproducibilityError(f"unsupported artifact audit for {builder}")
    source = _object(audit.get("source"), f"{builder} source")
    release_commit = source.get("release_commit")
    git_tree = source.get("git_tree")
    if not isinstance(release_commit, str) or _GIT_OID_PATTERN.fullmatch(release_commit) is None:
        raise ReproducibilityError(f"invalid release commit for {builder}")
    if not isinstance(git_tree, str) or _GIT_OID_PATTERN.fullmatch(git_tree) is None:
        raise ReproducibilityError(f"invalid Git tree for {builder}")
    environment = _object(audit.get("environment"), f"{builder} environment")
    if (
        environment.get("python_version") != "3.11.9"
        or environment.get("implementation") != "CPython"
    ):
        raise ReproducibilityError(f"unsupported build environment for {builder}")
    expected_package = {
        "name": "koguard",
        "version": "0.1.0",
        "requires_python": ">=3.11,<3.12",
        "license_expression": "MIT",
        "runtime_dependencies": [],
    }
    if audit.get("package") != expected_package:
        raise ReproducibilityError(f"package metadata differs for {builder}")

    raw_artifacts = audit.get("artifacts")
    if not isinstance(raw_artifacts, list) or len(raw_artifacts) != 2:
        raise ReproducibilityError(f"artifact audit is incomplete for {builder}")
    artifacts: dict[str, dict[str, Any]] = {}
    for raw_artifact in raw_artifacts:
        artifact = _object(raw_artifact, f"{builder} artifact")
        kind = artifact.get("kind")
        if kind not in _EXPECTED_FILENAMES or kind in artifacts:
            raise ReproducibilityError(f"artifact kinds are invalid for {builder}")
        resolved_kind = cast(str, kind)
        filename = artifact.get("filename")
        if filename != _EXPECTED_FILENAMES[resolved_kind]:
            raise ReproducibilityError(f"artifact filename differs for {builder}")
        artifact_path = candidate / "dist" / cast(str, filename)
        if not artifact_path.is_file():
            raise ReproducibilityError(f"candidate artifact is missing for {builder}: {filename}")
        digest = artifact.get("sha256")
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise ReproducibilityError(f"artifact digest is invalid for {builder}: {filename}")
        size = artifact.get("size_bytes")
        if type(size) is not int or size <= 0:
            raise ReproducibilityError(f"artifact size is invalid for {builder}: {filename}")
        if artifact_path.stat().st_size != size or _hash_file(artifact_path) != digest:
            raise ReproducibilityError(f"artifact audit does not match files for {builder}")
        artifacts[resolved_kind] = {
            "kind": resolved_kind,
            "filename": filename,
            "size_bytes": size,
            "sha256": digest,
        }
    if set(artifacts) != set(_EXPECTED_FILENAMES):
        raise ReproducibilityError(f"artifact audit is incomplete for {builder}")
    return {
        "release_commit": release_commit,
        "git_tree": git_tree,
        "audit_sha256": _hash_file(audit_path),
        "artifacts": artifacts,
    }


def verify_candidate_root(
    candidate_root: Path,
    *,
    verified_at: datetime | None = None,
) -> dict[str, Any]:
    """Return an aggregate report only when all three candidate files are identical."""

    timestamp = verified_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ReproducibilityError("verified_at must include timezone information")
    candidates = {builder: _validated_candidate(candidate_root, builder) for builder in _BUILDERS}
    source_identities = {
        (candidate["release_commit"], candidate["git_tree"]) for candidate in candidates.values()
    }
    if len(source_identities) != 1:
        raise ReproducibilityError("candidate source identities differ across builders")
    release_commit, git_tree = next(iter(source_identities))
    baseline = candidates["Linux"]["artifacts"]
    if any(candidate["artifacts"] != baseline for candidate in candidates.values()):
        raise ReproducibilityError("candidate artifact hashes differ across builders")

    return {
        "schema_version": 1,
        "verified_at": timestamp.astimezone(UTC).isoformat(),
        "release_commit": release_commit,
        "git_tree": git_tree,
        "authoritative_builder": "Linux",
        "builders": list(_BUILDERS),
        "audits": [
            {
                "builder": builder,
                "sha256": candidates[builder]["audit_sha256"],
            }
            for builder in _BUILDERS
        ],
        "artifacts": [baseline[kind] for kind in ("wheel", "sdist")],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Verify downloaded CI candidates and write aggregate reproducibility evidence."""

    arguments = _parser().parse_args(argv)
    try:
        report = verify_candidate_root(arguments.candidate_root)
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            "release artifacts are reproducible; "
            f"commit={report['release_commit']}; builders={','.join(report['builders'])}"
        )
    except ReproducibilityError as exc:
        print(f"release reproducibility verification failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
