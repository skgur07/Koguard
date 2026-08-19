"""Cross-platform release artifact reproducibility tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from release.verify_reproducible_artifacts import (
    REPRODUCIBILITY_REPORT_SCHEMA_PATH,
    ReproducibilityError,
    verify_candidate_root,
)

_RELEASE_COMMIT = "a" * 40
_GIT_TREE = "b" * 40


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_candidate(root: Path, runner: str, *, wheel: bytes = b"wheel\n") -> None:
    candidate = root / f"koguard-0.1.0-candidate-{runner}-python311"
    dist = candidate / "dist"
    dist.mkdir(parents=True)
    wheel_path = dist / "koguard-0.1.0-py3-none-any.whl"
    sdist_path = dist / "koguard-0.1.0.tar.gz"
    wheel_path.write_bytes(wheel)
    sdist_path.write_bytes(b"sdist\n")
    report = {
        "schema_version": 1,
        "generated_at": "2026-08-19T00:00:00+00:00",
        "source": {"release_commit": _RELEASE_COMMIT, "git_tree": _GIT_TREE},
        "environment": {
            "python_version": "3.11.9",
            "implementation": "CPython",
            "platform": runner,
        },
        "package": {
            "name": "koguard",
            "version": "0.1.0",
            "requires_python": ">=3.11,<3.12",
            "license_expression": "MIT",
            "runtime_dependencies": [],
        },
        "artifacts": [
            {
                "kind": "wheel",
                "filename": wheel_path.name,
                "size_bytes": wheel_path.stat().st_size,
                "sha256": _sha256(wheel_path),
                "member_count": 1,
                "bundled_notices": ["notice"],
            },
            {
                "kind": "sdist",
                "filename": sdist_path.name,
                "size_bytes": sdist_path.stat().st_size,
                "sha256": _sha256(sdist_path),
                "member_count": 1,
                "release_evidence": ["LICENSE"],
            },
        ],
    }
    (candidate / f"release-audit-{runner}.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )


def test_reproducibility_report_schema_is_closed() -> None:
    schema = json.loads(REPRODUCIBILITY_REPORT_SCHEMA_PATH.read_text(encoding="utf-8"))

    assert schema["properties"]["schema_version"]["const"] == 1
    assert schema["properties"]["authoritative_builder"]["const"] == "Linux"
    assert schema["additionalProperties"] is False


def test_verify_candidate_root_accepts_identical_three_os_artifacts(tmp_path: Path) -> None:
    for runner in ("Linux", "Windows", "macOS"):
        _write_candidate(tmp_path, runner)

    report = verify_candidate_root(tmp_path)

    assert report["release_commit"] == _RELEASE_COMMIT
    assert report["git_tree"] == _GIT_TREE
    assert report["builders"] == ["Linux", "Windows", "macOS"]
    assert {artifact["kind"] for artifact in report["artifacts"]} == {"wheel", "sdist"}


def test_verify_candidate_root_rejects_cross_os_hash_mismatch(tmp_path: Path) -> None:
    _write_candidate(tmp_path, "Linux")
    _write_candidate(tmp_path, "Windows", wheel=b"windows-wheel\r\n")
    _write_candidate(tmp_path, "macOS")

    with pytest.raises(ReproducibilityError, match="hashes differ"):
        verify_candidate_root(tmp_path)
