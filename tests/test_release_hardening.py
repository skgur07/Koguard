"""PF-013 CI, artifact, clean-install, and rights hardening tests."""

import io
import json
import tarfile
import tomllib
import zipfile
from pathlib import Path

import pytest
from release.artifact_audit import (
    ReleaseAuditError,
    audit_distributions,
    validate_rights_manifest,
)
from release.clean_install_smoke import discover_artifacts

_WHEEL_NAME = "koguard-0.1.0-py3-none-any.whl"
_SDIST_NAME = "koguard-0.1.0.tar.gz"
_METADATA = """Metadata-Version: 2.4
Name: koguard
Version: 0.1.0
Requires-Python: >=3.11,<3.12
License-Expression: MIT
\n"""


def _write_wheel(
    path: Path,
    *,
    forbidden_member: str | None = None,
    metadata: str = _METADATA,
) -> None:
    members = {
        "koguard/__init__.py": b'__version__ = "0.1.0"\n',
        "koguard/data/NOTICE.md": b"notice\n",
        "koguard/data/KORCEN-MIT.txt": b"MIT\n",
        "koguard/data/CURSE-DETECTION-DATA-MIT.txt": b"MIT\n",
        "koguard-0.1.0.dist-info/METADATA": metadata.encode(),
        "koguard-0.1.0.dist-info/licenses/LICENSE": b"MIT\n",
        "koguard-0.1.0.dist-info/RECORD": b"",
    }
    if forbidden_member is not None:
        members[forbidden_member] = b"must not ship\n"
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)


def _write_sdist(
    path: Path,
    *,
    forbidden_member: str | None = None,
    metadata: str = _METADATA,
) -> None:
    root = "koguard-0.1.0"
    members = {
        "LICENSE": b"MIT\n",
        "README.md": b"# Koguard\n",
        "CHANGELOG.md": b"# Changelog\n",
        "SECURITY.md": b"# Security\n",
        "CONTRIBUTING.md": b"# Contributing\n",
        "pyproject.toml": b"[project]\nname='koguard'\n",
        "PKG-INFO": metadata.encode(),
        "src/koguard/data/NOTICE.md": b"notice\n",
        "src/koguard/data/KORCEN-MIT.txt": b"MIT\n",
        "src/koguard/data/CURSE-DETECTION-DATA-MIT.txt": b"MIT\n",
        "docs/release-hardening.md": b"# Release hardening\n",
        "docs/pf014-release-readiness.md": b"# PF-014\n",
        "evaluation/hidden_evaluation_report.py": b'"""Aggregate report."""\n',
        "evaluation/hidden-evaluation-attestation.schema.json": b"{}\n",
        "evaluation/hidden-evaluation-report.schema.json": b"{}\n",
        "release/release_report.py": b'"""Release report."""\n',
        "release/release-report.schema.json": b"{}\n",
        "release/rights-manifest.v1.json": b"{}\n",
        "release/testpypi-evidence.schema.json": b"{}\n",
    }
    if forbidden_member is not None:
        members[forbidden_member] = b"must not ship\n"
    with tarfile.open(path, "w:gz") as archive:
        for relative_name, content in members.items():
            info = tarfile.TarInfo(f"{root}/{relative_name}")
            info.size = len(content)
            archive.addfile(info, io.BytesIO(content))


def test_release_audit_records_hash_size_metadata_and_zero_runtime_dependencies(
    tmp_path: Path,
) -> None:
    _write_wheel(tmp_path / _WHEEL_NAME)
    _write_sdist(tmp_path / _SDIST_NAME)

    report = audit_distributions(tmp_path)

    assert report["schema_version"] == 1
    assert report["package"] == {
        "name": "koguard",
        "version": "0.1.0",
        "requires_python": ">=3.11,<3.12",
        "license_expression": "MIT",
        "runtime_dependencies": [],
    }
    assert {artifact["kind"] for artifact in report["artifacts"]} == {"wheel", "sdist"}
    assert all(len(artifact["sha256"]) == 64 for artifact in report["artifacts"])
    assert all(artifact["size_bytes"] > 0 for artifact in report["artifacts"])


def test_release_audit_accepts_equivalent_requires_python_order(tmp_path: Path) -> None:
    reordered_metadata = _METADATA.replace(">=3.11,<3.12", "<3.12,>=3.11")
    _write_wheel(tmp_path / _WHEEL_NAME, metadata=reordered_metadata)
    _write_sdist(tmp_path / _SDIST_NAME, metadata=reordered_metadata)

    report = audit_distributions(tmp_path)

    assert report["package"]["requires_python"] == ">=3.11,<3.12"


def test_release_audit_rejects_non_runtime_payload_in_wheel(tmp_path: Path) -> None:
    _write_wheel(tmp_path / _WHEEL_NAME, forbidden_member="evaluation/raw.csv")
    _write_sdist(tmp_path / _SDIST_NAME)

    with pytest.raises(ReleaseAuditError, match="forbidden wheel member"):
        audit_distributions(tmp_path)


def test_release_audit_rejects_unexpected_wheel_root(tmp_path: Path) -> None:
    _write_wheel(tmp_path / _WHEEL_NAME, forbidden_member="secrets/config.json")
    _write_sdist(tmp_path / _SDIST_NAME)

    with pytest.raises(ReleaseAuditError, match="unexpected wheel member root"):
        audit_distributions(tmp_path)


def test_release_audit_rejects_unsafe_archive_member(tmp_path: Path) -> None:
    _write_wheel(tmp_path / _WHEEL_NAME, forbidden_member="../outside.py")
    _write_sdist(tmp_path / _SDIST_NAME)

    with pytest.raises(ReleaseAuditError, match="unsafe wheel member name"):
        audit_distributions(tmp_path)


def test_release_audit_rejects_raw_dataset_in_sdist(tmp_path: Path) -> None:
    _write_wheel(tmp_path / _WHEEL_NAME)
    _write_sdist(tmp_path / _SDIST_NAME, forbidden_member="evaluation/external/dataset.txt")

    with pytest.raises(ReleaseAuditError, match="forbidden sdist member"):
        audit_distributions(tmp_path)


def test_rights_manifest_rejects_unapproved_public_payload(tmp_path: Path) -> None:
    manifest_path = tmp_path / "rights.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_license": "MIT",
                "sources": [
                    {
                        "source_id": "unapproved-source",
                        "rights_status": "pending",
                        "payload_in_artifacts": True,
                        "runtime_dependency": False,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ReleaseAuditError, match="unapproved public payload"):
        validate_rights_manifest(manifest_path)


def test_clean_install_discovers_exactly_one_wheel_and_sdist(tmp_path: Path) -> None:
    wheel = tmp_path / _WHEEL_NAME
    sdist = tmp_path / _SDIST_NAME
    wheel.touch()
    sdist.touch()

    assert discover_artifacts(tmp_path) == (wheel, sdist)

    (tmp_path / "koguard-0.1.0-2-py3-none-any.whl").touch()
    with pytest.raises(ValueError, match="exactly one wheel"):
        discover_artifacts(tmp_path)


def test_project_metadata_and_release_documents_are_publication_complete() -> None:
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["license"] == "MIT"
    assert project["license-files"] == [
        "LICENSE",
        "src/koguard/data/KORCEN-MIT.txt",
        "src/koguard/data/CURSE-DETECTION-DATA-MIT.txt",
    ]
    assert project["authors"] == [{"name": "skgur07"}]
    assert project["dependencies"] == []
    assert project["requires-python"] == ">=3.11,<3.12"
    assert project["urls"]["Repository"] == "https://github.com/skgur07/Koguard"
    assert pyproject["build-system"]["requires"] == ["hatchling==1.31.0"]
    for path in (
        Path("LICENSE"),
        Path("CHANGELOG.md"),
        Path("SECURITY.md"),
        Path("CONTRIBUTING.md"),
        Path("docs/release-hardening.md"),
        Path("docs/pf014-release-readiness.md"),
        Path("release/rights-manifest.v1.json"),
        Path("release/release_report.py"),
        Path("release/release-report.schema.json"),
        Path("release/testpypi-evidence.schema.json"),
        Path("evaluation/hidden_evaluation_report.py"),
        Path("evaluation/hidden-evaluation-attestation.schema.json"),
        Path("evaluation/hidden-evaluation-report.schema.json"),
        Path(".mailmap"),
    ):
        assert path.is_file(), path


def test_mailmap_unifies_the_maintainers_previous_git_identity() -> None:
    mailmap = Path(".mailmap").read_text(encoding="utf-8").splitlines()

    assert mailmap == ["skgur07 <pigjaoki0970@gmail.com> s23019 <s23019@gsm.hs.kr>"]


def test_rights_manifest_keeps_unapproved_payload_out_of_public_artifacts() -> None:
    manifest = json.loads(Path("release/rights-manifest.v1.json").read_text(encoding="utf-8"))

    assert manifest["schema_version"] == 1
    assert manifest["project_license"] == "MIT"
    assert all(
        source["rights_status"] == "approved" or source["payload_in_artifacts"] is False
        for source in manifest["sources"]
    )
    assert all(source["runtime_dependency"] is False for source in manifest["sources"])


def test_ci_matrix_pins_actions_and_runs_complete_release_gate() -> None:
    workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    assert "contents: read" in workflow
    assert "ubuntu-latest" in workflow
    assert "windows-latest" in workflow
    assert "macos-latest" in workflow
    assert 'python-version: "3.11.9"' in workflow
    assert "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1" in workflow
    assert "actions/setup-python@5fda3b95a4ea91299a34e894583c3862153e4b97" in workflow
    assert "astral-sh/setup-uv@ae62891fec2bb8e7d6c99fc78c9fec3a63790f8d" in workflow
    assert "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a" in workflow
    assert "uses: actions/checkout@v" not in workflow
    assert "uses: actions/setup-python@v" not in workflow
    assert "uses: astral-sh/setup-uv@v" not in workflow
    for command in (
        "uv sync --frozen --all-extras --dev",
        "uv run ruff format --check .",
        "uv run ruff check .",
        "uv run mypy",
        "uv run pytest",
        "uv build",
        "uv run python -m evaluation.dictionary_provenance",
        "uv run python -m release.artifact_audit",
        "uv run python -m release.clean_install_smoke",
    ):
        assert command in workflow
