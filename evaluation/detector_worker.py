"""Isolated JSON worker for the Koguard/Korcen comparison runner."""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import platform
import sys
from email.parser import Parser
from hashlib import sha256
from importlib import metadata
from pathlib import Path
from typing import Any, Protocol, cast
from zipfile import BadZipFile, ZipFile

_PROTOCOL_VERSION = 1
_KOGUARD_PROFILE = "current-all-enabled"
_KORCEN_PROFILE = "korean-all"


class WorkerInputError(ValueError):
    """Raised for malformed parent-worker protocol input."""


class _KorcenModule(Protocol):
    def check(self, text: str, id: object | None = None, foreign: bool = False) -> bool:
        """Return whether Korcen detects the supplied text."""


class _DiscardingTextSink(io.TextIOBase):
    """Discard detector output while remembering whether any was emitted."""

    def __init__(self) -> None:
        self.had_output = False

    def write(self, value: str) -> int:
        self.had_output = self.had_output or bool(value)
        return len(value)


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise WorkerInputError
    return value


def _normalize_package(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")


def _read_wheel_identity(path: Path) -> tuple[str, str]:
    try:
        with ZipFile(path) as archive:
            names = sorted(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            if len(names) != 1:
                raise WorkerInputError
            message = Parser().parsestr(archive.read(names[0]).decode("utf-8"))
    except (OSError, UnicodeError, BadZipFile, KeyError) as exc:
        raise WorkerInputError from exc
    package = message.get("Name")
    version = message.get("Version")
    if not package or not version:
        raise WorkerInputError
    return package, version


def _parse_request(payload: object) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
    if not isinstance(payload, dict):
        raise WorkerInputError
    request = cast(dict[str, object], payload)
    if request.get("protocol_version") != _PROTOCOL_VERSION:
        raise WorkerInputError
    fields = {
        name: _require_str(request.get(name))
        for name in (
            "detector_id",
            "package",
            "version",
            "profile",
            "artifact_path",
            "artifact_sha256",
        )
    }
    raw_cases = request.get("cases")
    if not isinstance(raw_cases, list):
        raise WorkerInputError
    cases: list[tuple[str, str]] = []
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise WorkerInputError
        case = cast(dict[str, object], raw_case)
        cases.append((_require_str(case.get("case_id")), cast(str, case.get("text"))))
        if not isinstance(case.get("text"), str):
            raise WorkerInputError
    if len({case_id for case_id, _ in cases}) != len(cases):
        raise WorkerInputError
    return fields, tuple(cases)


def _verify_artifact(fields: dict[str, str]) -> Path:
    path = Path(fields["artifact_path"])
    try:
        digest = sha256()
        with path.open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise WorkerInputError from exc
    if digest.hexdigest() != fields["artifact_sha256"]:
        raise WorkerInputError
    package, version = _read_wheel_identity(path)
    if (
        _normalize_package(package) != _normalize_package(fields["package"])
        or version != fields["version"]
    ):
        raise WorkerInputError
    return path


def _dependencies(names: tuple[str, ...]) -> list[dict[str, str]]:
    result = []
    for name in sorted(names):
        try:
            version = metadata.version(name)
        except metadata.PackageNotFoundError as exc:
            raise RuntimeError(f"missing dependency: {name}") from exc
        result.append({"package": name, "version": version})
    return result


def _run_koguard(
    profile: str, cases: tuple[tuple[str, str], ...]
) -> tuple[
    dict[str, bool],
    dict[str, str | bool | int | float],
    list[dict[str, Any]],
    list[dict[str, str]],
]:
    if profile != _KOGUARD_PROFILE:
        raise WorkerInputError
    from koguard import EngineConfig, KoguardEngine

    config = EngineConfig(
        exact_matching=True,
        repeated_matching=True,
        separator_matching=True,
        whitespace_gap_matching=True,
        mixed_gap_matching=True,
        choseong_matching=True,
        alias_matching=True,
        keyboard_matching=True,
        jamo_composition_matching=True,
        segmented_input_matching=True,
        fuzzy_matching=True,
    )
    engine = KoguardEngine(config=config)
    predictions: list[dict[str, Any]] = []
    for case_id, text in cases:
        result = engine.check(text)
        matches = []
        for match in result.matches:
            if match.start is None or match.end is None:
                raise RuntimeError("Koguard returned a match without an original span")
            matches.append(
                {
                    "start": match.start,
                    "end": match.end,
                    "canonical_term": match.term,
                }
            )
        predictions.append({"case_id": case_id, "detected": result.detected, "matches": matches})
    capabilities = {
        "sentence": True,
        "occurrences": True,
        "spans": True,
        "canonical_terms": True,
    }
    settings: dict[str, str | bool | int | float] = {
        "alias_matching": config.alias_matching,
        "choseong_matching": config.choseong_matching,
        "exact_matching": config.exact_matching,
        "fuzzy_matching": config.fuzzy_matching,
        "fuzzy_max_distance": config.fuzzy_max_distance,
        "fuzzy_max_index_entries": config.fuzzy_max_index_entries,
        "fuzzy_max_operations": config.fuzzy_max_operations,
        "fuzzy_max_term_length": config.fuzzy_max_term_length,
        "fuzzy_min_score": config.fuzzy_min_score,
        "fuzzy_min_term_length": config.fuzzy_min_term_length,
        "jamo_composition_matching": config.jamo_composition_matching,
        "keyboard_matching": config.keyboard_matching,
        "max_input_length": config.max_input_length,
        "max_whitespace_gap": config.max_whitespace_gap,
        "mixed_gap_matching": config.mixed_gap_matching,
        "obfuscation_separators": "".join(sorted(config.obfuscation_separators)),
        "repeat_reduction_threshold": config.repeat_reduction_threshold,
        "repeated_matching": config.repeated_matching,
        "segmented_input_matching": config.segmented_input_matching,
        "separator_matching": config.separator_matching,
        "unicode_form": config.unicode_form,
        "whitespace_gap_matching": config.whitespace_gap_matching,
    }
    return capabilities, settings, predictions, []


def _run_korcen(
    profile: str, cases: tuple[tuple[str, str], ...]
) -> tuple[
    dict[str, bool],
    dict[str, str | bool | int | float],
    list[dict[str, Any]],
    list[dict[str, str]],
]:
    if profile != _KORCEN_PROFILE:
        raise WorkerInputError
    korcen_package = importlib.import_module("korcen")
    korcen = cast(_KorcenModule, korcen_package.korcen)

    predictions = []
    for case_id, text in cases:
        detected = korcen.check(text, foreign=False)
        if type(detected) is not bool:
            raise RuntimeError("Korcen returned a non-boolean value")
        predictions.append({"case_id": case_id, "detected": detected, "matches": None})
    capabilities = {
        "sentence": True,
        "occurrences": False,
        "spans": False,
        "canonical_terms": False,
    }
    return (
        capabilities,
        {"foreign": False},
        predictions,
        _dependencies(("better-profanity", "colorama")),
    )


def _execute(fields: dict[str, str], cases: tuple[tuple[str, str], ...]) -> dict[str, object]:
    artifact = _verify_artifact(fields)
    sys.path.insert(0, str(artifact))
    detector_id = fields["detector_id"]
    if detector_id == "koguard":
        capabilities, settings, predictions, dependencies = _run_koguard(fields["profile"], cases)
    elif detector_id == "korcen":
        capabilities, settings, predictions, dependencies = _run_korcen(fields["profile"], cases)
    else:
        raise WorkerInputError
    return {
        "protocol_version": _PROTOCOL_VERSION,
        "detector_id": detector_id,
        "package": _normalize_package(fields["package"]),
        "version": fields["version"],
        "profile": fields["profile"],
        "settings": settings,
        "capabilities": capabilities,
        "runtime": {
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "dependencies": dependencies,
            "suppressed_output": False,
        },
        "predictions": predictions,
    }


def main() -> int:
    """Read one request from stdin and emit exactly one protocol response."""

    protocol_stdout = sys.stdout
    captured_stdout = _DiscardingTextSink()
    captured_stderr = _DiscardingTextSink()
    stage = "input"
    try:
        request = json.loads(sys.stdin.read())
        fields, cases = _parse_request(request)
        stage = "detector"
        with (
            contextlib.redirect_stdout(captured_stdout),
            contextlib.redirect_stderr(captured_stderr),
        ):
            response = _execute(fields, cases)
        runtime = cast(dict[str, object], response["runtime"])
        runtime["suppressed_output"] = captured_stdout.had_output or captured_stderr.had_output
        print(json.dumps(response, ensure_ascii=False), file=protocol_stdout)
        return 0
    except Exception as exc:
        response = {
            "protocol_version": _PROTOCOL_VERSION,
            "error": {"stage": stage, "type": type(exc).__name__},
        }
        print(json.dumps(response), file=protocol_stdout)
        return 1


if __name__ == "__main__":
    sys.exit(main())
