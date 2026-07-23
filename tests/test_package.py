"""Tests for the top-level package API."""

import koguard


def test_package_exports_installed_version() -> None:
    assert koguard.__version__ == "0.1.0"
