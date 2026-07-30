"""Tests for the top-level package API."""

import tomllib
from pathlib import Path

import koguard


def test_package_exports_installed_version() -> None:
    assert koguard.__version__ == "0.1.0"


def test_sdist_includes_benchmark_harness_used_by_packaged_tests() -> None:
    project_config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    sdist_includes = project_config["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]

    assert "/benchmarks" in sdist_includes
