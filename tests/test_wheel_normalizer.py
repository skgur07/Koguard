"""Cross-platform wheel ZIP metadata normalization tests."""

from __future__ import annotations

import hashlib
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from release.normalize_wheel import normalize_wheel_metadata


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_wheel(path: Path, *, create_system: int) -> None:
    with ZipFile(path, "w") as archive:
        archive.comment = b"koguard-test-wheel"
        for name, content in (
            ("koguard/__init__.py", b'__version__ = "0.1.0"\n'),
            ("koguard-0.1.0.dist-info/WHEEL", b"Wheel-Version: 1.0\n"),
        ):
            info = ZipInfo(name, date_time=(2020, 2, 2, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.create_system = create_system
            info.external_attr = 0o100644 << 16
            archive.writestr(info, content)


def test_normalizer_makes_windows_and_unix_wheels_byte_identical(tmp_path: Path) -> None:
    unix_wheel = tmp_path / "unix.whl"
    windows_wheel = tmp_path / "windows.whl"
    _write_wheel(unix_wheel, create_system=3)
    _write_wheel(windows_wheel, create_system=0)
    assert _sha256(unix_wheel) != _sha256(windows_wheel)

    unix_digest = normalize_wheel_metadata(unix_wheel)
    windows_digest = normalize_wheel_metadata(windows_wheel)

    assert unix_digest == windows_digest
    assert unix_wheel.read_bytes() == windows_wheel.read_bytes()
    with ZipFile(windows_wheel) as archive:
        assert archive.comment == b"koguard-test-wheel"
        assert all(info.create_system == 3 for info in archive.infolist())
        assert archive.read("koguard/__init__.py") == b'__version__ = "0.1.0"\n'


def test_normalizer_is_byte_idempotent(tmp_path: Path) -> None:
    wheel = tmp_path / "koguard-0.1.0-py3-none-any.whl"
    _write_wheel(wheel, create_system=0)

    first_digest = normalize_wheel_metadata(wheel)
    first_bytes = wheel.read_bytes()
    second_digest = normalize_wheel_metadata(wheel)

    assert second_digest == first_digest
    assert wheel.read_bytes() == first_bytes
