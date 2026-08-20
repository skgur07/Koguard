"""Normalize wheel ZIP creator metadata for byte-identical cross-platform builds."""

from __future__ import annotations

import argparse
import copy
import hashlib
import os
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path
from zipfile import BadZipFile, LargeZipFile, ZipFile

_CANONICAL_CREATE_SYSTEM = 3


class WheelNormalizationError(ValueError):
    """Raised when a built wheel cannot be normalized safely."""


def normalize_wheel_metadata(wheel_path: Path) -> str:
    """Rewrite one wheel with canonical Unix ZIP creator metadata and return its SHA-256."""

    wheel = wheel_path.resolve()
    if wheel.suffix != ".whl" or not wheel.is_file():
        raise WheelNormalizationError("wheel path must identify one existing .whl file")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{wheel.name}.",
        suffix=".tmp",
        dir=wheel.parent,
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        with ZipFile(wheel, "r") as source:
            members = source.infolist()
            names = [member.filename for member in members]
            if len(names) != len(set(names)):
                raise WheelNormalizationError("wheel contains duplicate archive members")
            with ZipFile(temporary, "w", allowZip64=True) as target:
                target.comment = source.comment
                for member in members:
                    normalized = copy.copy(member)
                    normalized.create_system = _CANONICAL_CREATE_SYSTEM
                    target.writestr(normalized, source.read(member))
        os.replace(temporary, wheel)
    except WheelNormalizationError:
        raise
    except (OSError, BadZipFile, LargeZipFile, RuntimeError, ValueError) as exc:
        raise WheelNormalizationError("failed to normalize wheel metadata") from exc
    finally:
        temporary.unlink(missing_ok=True)

    return hashlib.sha256(wheel.read_bytes()).hexdigest()


def discover_wheel(dist_dir: Path) -> Path:
    """Return exactly one wheel from a build output directory."""

    wheels = sorted(dist_dir.glob("*.whl"))
    if len(wheels) != 1:
        raise WheelNormalizationError(f"expected exactly one wheel, found {len(wheels)}")
    return wheels[0]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Normalize one built wheel and print only its filename and canonical hash."""

    arguments = _parser().parse_args(argv)
    try:
        wheel = discover_wheel(arguments.dist_dir)
        digest = normalize_wheel_metadata(wheel)
    except WheelNormalizationError as exc:
        print(f"wheel normalization failed: {exc}", file=sys.stderr)
        return 1
    print(f"normalized {wheel.name}; sha256={digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
