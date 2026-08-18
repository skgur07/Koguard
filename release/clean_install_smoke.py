"""Install built Koguard artifacts in isolated environments and run the quickstart."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from hashlib import sha256
from pathlib import Path

_SMOKE_CODE = """
from importlib.metadata import requires, version
from koguard import KoguardEngine

assert version("koguard") == "0.1.0"
assert not (requires("koguard") or [])
engine = KoguardEngine()
assert engine.contains("시발")
assert engine.contains("틀딱")
assert engine.contains("sibal")
assert not engine.contains("오늘 저녁에 같이 게임할래?")
result = engine.check("시발")
assert result.detected and result.matches[0].term == "시발"
print("koguard clean-install smoke: ok")
"""


def discover_artifacts(dist_dir: Path) -> tuple[Path, Path]:
    """Return exactly one wheel and one sdist for clean-install checks."""

    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1:
        raise ValueError(f"expected exactly one wheel, found {len(wheels)}")
    if len(sdists) != 1:
        raise ValueError(f"expected exactly one sdist, found {len(sdists)}")
    return wheels[0], sdists[0]


def _venv_python(environment: Path) -> Path:
    if sys.platform == "win32":
        return environment / "Scripts" / "python.exe"
    return environment / "bin" / "python"


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def smoke_artifact(artifact: Path, *, uv_executable: str) -> dict[str, object]:
    """Install one local artifact without runtime dependencies and run an isolated probe."""

    artifact = artifact.resolve()
    with tempfile.TemporaryDirectory(prefix="koguard-release-smoke-") as directory:
        root = Path(directory)
        environment = root / "venv"
        subprocess.run(
            [
                uv_executable,
                "venv",
                "--no-project",
                "--python",
                sys.executable,
                str(environment),
            ],
            check=True,
            cwd=root,
        )
        python = _venv_python(environment)
        subprocess.run(
            [
                uv_executable,
                "pip",
                "install",
                "--offline",
                "--python",
                str(python),
                "--no-deps",
                str(artifact),
            ],
            check=True,
            cwd=root,
        )
        completed = subprocess.run(
            [str(python), "-I", "-c", _SMOKE_CODE],
            check=True,
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    return {
        "filename": artifact.name,
        "sha256": _hash_file(artifact),
        "status": "passed",
        "probe": completed.stdout.strip(),
    }


def run_smoke(dist_dir: Path, *, uv_executable: str | None = None) -> dict[str, object]:
    """Run the clean-install probe for the wheel and source distribution."""

    executable = uv_executable or shutil.which("uv")
    if executable is None:
        raise RuntimeError("uv executable is required for clean-install smoke tests")
    return {
        "schema_version": 1,
        "artifacts": [
            smoke_artifact(artifact, uv_executable=executable)
            for artifact in discover_artifacts(dist_dir)
        ],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist-dir", type=Path, default=Path("dist"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run both clean-install checks and print their machine-readable result."""

    arguments = _parser().parse_args(argv)
    print(json.dumps(run_smoke(arguments.dist_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
