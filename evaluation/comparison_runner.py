"""Run a reproducible, privacy-preserving detector comparison on a gold corpus."""

from __future__ import annotations

import argparse
import copy
import json
import platform
import subprocess
import sys
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from email.parser import Parser
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from zipfile import BadZipFile, ZipFile

from evaluation.corpus_validator import CORPUS_SCHEMA_PATH, validate_corpus_paths

COMPARISON_REPORT_SCHEMA_PATH = Path(__file__).with_name("comparison-report.schema.json")
RUNNER_VERSION = "1"
KORCEN_VERSION = "1.0.3"
KORCEN_PROFILE = "korean-all"
KORCEN_WHEEL_FILENAME = "korcen-1.0.3-py3-none-any.whl"
KORCEN_WHEEL_SHA256 = "5139fb973ab40f2f4caaa722c97553397993e6a83a463a1098a85061834fb446"
KOGUARD_PROFILE = "current-all-enabled"
KOGUARD_PROFILES = (KOGUARD_PROFILE,)
_WORKER_PROTOCOL_VERSION = 1
_WORKER_TIMEOUT_SECONDS = 120


class ComparisonError(ValueError):
    """Raised when comparison inputs or isolated detector output are invalid."""


@dataclass(frozen=True, slots=True)
class DetectorCapabilities:
    """Machine-readable detector output capabilities."""

    sentence: bool
    occurrences: bool
    spans: bool
    canonical_terms: bool


@dataclass(frozen=True, slots=True)
class PredictionMatch:
    """One detector occurrence, retained only until aggregate metrics are built."""

    start: int
    end: int
    canonical_term: str


@dataclass(frozen=True, slots=True)
class Prediction:
    """One detector prediction keyed by the immutable gold case identifier."""

    case_id: str
    detected: bool
    matches: tuple[PredictionMatch, ...] | None


@dataclass(frozen=True, slots=True)
class RuntimeMetadata:
    """Non-sensitive metadata reported by an isolated detector process."""

    python_version: str
    implementation: str
    platform: str
    dependencies: tuple[tuple[str, str], ...]
    suppressed_output: bool


@dataclass(frozen=True, slots=True)
class DetectorRun:
    """Validated result returned by one detector worker."""

    detector_id: str
    package: str
    version: str
    profile: str
    capabilities: DetectorCapabilities
    runtime: RuntimeMetadata
    predictions: tuple[Prediction, ...]
    settings: tuple[tuple[str, str | bool | int | float], ...] = ()


@dataclass(frozen=True, slots=True)
class DetectorSpec:
    """Artifact and interpreter selected for one comparison participant."""

    detector_id: str
    package: str
    expected_version: str
    profile: str
    artifact_path: Path
    python_executable: Path
    expected_sha256: str | None


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    """Verified wheel identity included in the report."""

    package: str
    version: str
    filename: str
    sha256: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class ComparisonReport:
    """JSON-serializable versioned comparison result."""

    _payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Return a defensive copy suitable for JSON serialization."""

        return copy.deepcopy(self._payload)


@dataclass(frozen=True, slots=True)
class _GoldMatch:
    start: int
    end: int
    canonical_term: str


@dataclass(frozen=True, slots=True)
class _GoldCase:
    case_id: str
    text: str
    label: str
    matches: tuple[_GoldMatch, ...]
    slices: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _CorpusData:
    cases: tuple[_GoldCase, ...]
    files: tuple[tuple[str, str], ...]
    sha256: str


WorkerRunner = Callable[[DetectorSpec, Sequence[tuple[str, str]]], DetectorRun]


def make_korcen_spec(wheel_path: Path, python_executable: Path) -> DetectorSpec:
    """Create a spec only for the exact, reviewed Korcen 1.0.3 wheel."""

    spec = DetectorSpec(
        detector_id="korcen",
        package="korcen",
        expected_version=KORCEN_VERSION,
        profile=KORCEN_PROFILE,
        artifact_path=wheel_path,
        python_executable=python_executable,
        expected_sha256=KORCEN_WHEEL_SHA256,
    )
    try:
        _inspect_wheel(spec)
    except ComparisonError as exc:
        if "SHA-256" in str(exc):
            raise ComparisonError("Korcen artifact SHA-256 mismatch") from exc
        raise
    return spec


def make_koguard_spec(
    wheel_path: Path,
    python_executable: Path,
    *,
    profile: str = KOGUARD_PROFILE,
) -> DetectorSpec:
    """Create a spec for the selected Koguard wheel and current explicit profile."""

    if profile not in KOGUARD_PROFILES:
        raise ComparisonError(f"unsupported Koguard profile: {profile}")
    package, version = _read_wheel_identity(wheel_path)
    if _normalize_package(package) != "koguard":
        raise ComparisonError("Koguard artifact package mismatch")
    return DetectorSpec(
        detector_id="koguard",
        package="koguard",
        expected_version=version,
        profile=profile,
        artifact_path=wheel_path,
        python_executable=python_executable,
        expected_sha256=None,
    )


def run_comparison(
    corpus_paths: Sequence[Path],
    detector_specs: Sequence[DetectorSpec],
    *,
    worker_runner: WorkerRunner | None = None,
    generated_at: datetime | None = None,
) -> ComparisonReport:
    """Evaluate every non-review gold case without allowing detectors to mutate gold."""

    if not detector_specs:
        raise ComparisonError("at least one detector spec is required")
    detector_ids = [spec.detector_id for spec in detector_specs]
    if len(detector_ids) != len(set(detector_ids)):
        raise ComparisonError("detector IDs must be unique")

    validate_corpus_paths(corpus_paths)
    corpus = _load_validated_corpus(corpus_paths)
    evaluated = tuple(case for case in corpus.cases if case.label != "review")
    if not evaluated:
        raise ComparisonError("corpus contains no automatically evaluable cases")
    case_inputs = tuple((case.case_id, case.text) for case in evaluated)
    artifacts = tuple(_inspect_wheel(spec) for spec in detector_specs)
    runner = worker_runner or _invoke_worker
    runs = tuple(runner(spec, case_inputs) for spec in detector_specs)

    prediction_maps: list[dict[str, Prediction]] = []
    for spec, artifact, run in zip(detector_specs, artifacts, runs, strict=True):
        prediction_maps.append(_validate_run(spec, artifact, run, evaluated))

    configuration = {
        "runner_version": RUNNER_VERSION,
        "corpus_sha256": corpus.sha256,
        "detectors": [
            {
                "detector_id": spec.detector_id,
                "package": artifact.package,
                "version": artifact.version,
                "profile": spec.profile,
                "artifact_sha256": artifact.sha256,
                "settings": dict(run.settings),
            }
            for spec, artifact, run in zip(detector_specs, artifacts, runs, strict=True)
        ],
    }
    configuration_sha = _canonical_sha256(configuration)
    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None:
        raise ComparisonError("generated_at must include timezone information")

    detector_reports = [
        _build_detector_report(run, artifact, evaluated, predictions)
        for run, artifact, predictions in zip(runs, artifacts, prediction_maps, strict=True)
    ]
    payload: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": timestamp.astimezone(UTC).isoformat(),
        "corpus": {
            "sha256": corpus.sha256,
            "files": [
                {"corpus_id": corpus_id, "sha256": file_sha} for corpus_id, file_sha in corpus.files
            ],
            "case_count": len(corpus.cases),
            "evaluated_case_count": len(evaluated),
            "excluded_review_count": len(corpus.cases) - len(evaluated),
        },
        "runner": {
            "name": "koguard-comparison-runner",
            "version": RUNNER_VERSION,
            "python_version": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "configuration_sha256": configuration_sha,
        },
        "detectors": detector_reports,
        "case_results": _build_case_results(evaluated, runs, prediction_maps),
    }
    return ComparisonReport(payload)


def _discover_corpus_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    schema_path = CORPUS_SCHEMA_PATH.resolve()
    discovered: set[Path] = set()
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            discovered.update(
                candidate.resolve()
                for candidate in path.rglob("*.json")
                if candidate.resolve() != schema_path
            )
        elif path.is_file() and path.resolve() != schema_path:
            discovered.add(path)
    return tuple(sorted(discovered, key=lambda item: item.as_posix()))


def _load_validated_corpus(paths: Sequence[Path]) -> _CorpusData:
    documents: list[tuple[str, dict[str, object]]] = []
    for path in _discover_corpus_files(paths):
        payload = cast(dict[str, object], json.loads(path.read_text(encoding="utf-8")))
        corpus_id = cast(str, payload["corpus_id"])
        documents.append((corpus_id, payload))

    cases: list[_GoldCase] = []
    files: list[tuple[str, str]] = []
    canonical_documents: list[dict[str, object]] = []
    for corpus_id, payload in sorted(documents, key=lambda item: item[0]):
        files.append((corpus_id, _canonical_sha256(payload)))
        canonical_documents.append(payload)
        for raw_case in cast(list[object], payload["cases"]):
            case = cast(dict[str, object], raw_case)
            matches = tuple(
                _GoldMatch(
                    start=cast(int, match["start"]),
                    end=cast(int, match["end"]),
                    canonical_term=cast(str, match["canonical_term"]),
                )
                for match in cast(list[dict[str, object]], case["expected_matches"])
            )
            cases.append(
                _GoldCase(
                    case_id=cast(str, case["id"]),
                    text=cast(str, case["text"]),
                    label=cast(str, case["label"]),
                    matches=matches,
                    slices=tuple(cast(list[str], case["slices"])),
                )
            )
    return _CorpusData(
        cases=tuple(cases),
        files=tuple(files),
        sha256=_canonical_sha256(canonical_documents),
    )


def _canonical_sha256(payload: object) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256(serialized).hexdigest()


def _normalize_package(value: str) -> str:
    return value.lower().replace("_", "-").replace(".", "-")


def _read_wheel_identity(path: Path) -> tuple[str, str]:
    try:
        with ZipFile(path) as archive:
            metadata_names = sorted(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            if len(metadata_names) != 1:
                raise ComparisonError("artifact must contain exactly one wheel METADATA file")
            message = Parser().parsestr(archive.read(metadata_names[0]).decode("utf-8"))
    except (OSError, UnicodeError, BadZipFile, KeyError) as exc:
        raise ComparisonError("failed to read detector wheel metadata") from exc
    package = message.get("Name")
    version = message.get("Version")
    if not package or not version:
        raise ComparisonError("detector wheel metadata is missing package name or version")
    return package, version


def _inspect_wheel(spec: DetectorSpec) -> ArtifactMetadata:
    try:
        digest, size_bytes = _sha256_file(spec.artifact_path)
    except OSError as exc:
        raise ComparisonError(f"{spec.detector_id} artifact is not readable") from exc
    if spec.expected_sha256 is not None and digest != spec.expected_sha256:
        raise ComparisonError(f"{spec.detector_id} artifact SHA-256 mismatch")
    package, version = _read_wheel_identity(spec.artifact_path)
    if _normalize_package(package) != _normalize_package(spec.package):
        raise ComparisonError(f"{spec.detector_id} artifact package mismatch")
    if version != spec.expected_version:
        raise ComparisonError(f"{spec.detector_id} artifact version mismatch")
    return ArtifactMetadata(
        package=_normalize_package(package),
        version=version,
        filename=spec.artifact_path.name,
        sha256=digest,
        size_bytes=size_bytes,
    )


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = sha256()
    size_bytes = 0
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
            size_bytes += len(chunk)
    return digest.hexdigest(), size_bytes


def _validate_run(
    spec: DetectorSpec,
    artifact: ArtifactMetadata,
    run: DetectorRun,
    cases: Sequence[_GoldCase],
) -> dict[str, Prediction]:
    if (
        run.detector_id != spec.detector_id
        or _normalize_package(run.package) != artifact.package
        or run.version != artifact.version
        or run.profile != spec.profile
    ):
        raise ComparisonError(f"{spec.detector_id} worker identity mismatch")
    if not run.capabilities.sentence:
        raise ComparisonError(f"{spec.detector_id} does not expose sentence output")
    if run.capabilities.occurrences != (
        run.capabilities.spans and run.capabilities.canonical_terms
    ):
        raise ComparisonError(f"{spec.detector_id} returned inconsistent capabilities")
    setting_names = [name for name, _ in run.settings]
    if len(setting_names) != len(set(setting_names)) or any(not name for name in setting_names):
        raise ComparisonError(f"{spec.detector_id} returned invalid settings")

    expected_ids = [case.case_id for case in cases]
    prediction_ids = [prediction.case_id for prediction in run.predictions]
    if (
        len(prediction_ids) != len(set(prediction_ids))
        or len(prediction_ids) != len(expected_ids)
        or set(prediction_ids) != set(expected_ids)
    ):
        raise ComparisonError(f"{spec.detector_id} prediction case IDs do not match the corpus")

    case_lengths = {case.case_id: len(case.text) for case in cases}
    predictions: dict[str, Prediction] = {}
    for prediction in run.predictions:
        if type(prediction.detected) is not bool:
            raise ComparisonError(f"{spec.detector_id} returned a non-boolean prediction")
        if not run.capabilities.occurrences:
            if prediction.matches is not None:
                raise ComparisonError(f"{spec.detector_id} does not support occurrence output")
        else:
            if prediction.matches is None:
                raise ComparisonError(f"{spec.detector_id} omitted occurrence output")
            if prediction.detected != bool(prediction.matches):
                raise ComparisonError(f"{spec.detector_id} sentence/occurrence output disagrees")
            for match in prediction.matches:
                if (
                    type(match.start) is not int
                    or type(match.end) is not int
                    or match.start < 0
                    or match.end <= match.start
                    or match.end > case_lengths[prediction.case_id]
                    or not match.canonical_term
                ):
                    raise ComparisonError(f"{spec.detector_id} returned an invalid occurrence")
        predictions[prediction.case_id] = prediction
    return predictions


def _safe_divide(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _metric_payload(tp: int, fp: int, fn: int, *, tn: int | None = None) -> dict[str, Any]:
    counts: dict[str, int] = {"tp": tp, "fp": fp, "fn": fn}
    if tn is not None:
        counts["tn"] = tn
    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall
        else None
    )
    payload: dict[str, Any] = {
        "counts": counts,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }
    if tn is not None:
        payload["accuracy"] = _safe_divide(tp + tn, tp + fp + fn + tn)
    return payload


def _sentence_outcome(gold_detected: bool, detected: bool) -> str:
    if gold_detected:
        return "tp" if detected else "fn"
    return "fp" if detected else "tn"


def _sentence_metrics(
    cases: Sequence[_GoldCase], predictions: Mapping[str, Prediction]
) -> dict[str, Any]:
    counts: Counter[str] = Counter(
        _sentence_outcome(bool(case.matches), predictions[case.case_id].detected) for case in cases
    )
    return _metric_payload(counts["tp"], counts["fp"], counts["fn"], tn=counts["tn"])


def _counter_metrics(gold: Counter[object], predicted: Counter[object]) -> dict[str, Any]:
    true_positive = sum((gold & predicted).values())
    return _metric_payload(
        true_positive,
        sum(predicted.values()) - true_positive,
        sum(gold.values()) - true_positive,
    )


def _occurrence_metrics(
    cases: Sequence[_GoldCase],
    predictions: Mapping[str, Prediction],
    capabilities: DetectorCapabilities,
) -> dict[str, Any]:
    if not capabilities.occurrences:
        return {
            "status": "unsupported",
            "reason": "detector does not expose occurrence spans or canonical terms",
        }

    exact_gold: Counter[object] = Counter()
    exact_predicted: Counter[object] = Counter()
    span_gold: Counter[object] = Counter()
    span_predicted: Counter[object] = Counter()
    canonical_gold: Counter[object] = Counter()
    canonical_predicted: Counter[object] = Counter()
    for case in cases:
        for match in case.matches:
            exact_gold[(case.case_id, match.start, match.end, match.canonical_term)] += 1
            span_gold[(case.case_id, match.start, match.end)] += 1
            canonical_gold[(case.case_id, match.canonical_term)] += 1
        for predicted_match in predictions[case.case_id].matches or ():
            exact_predicted[
                (
                    case.case_id,
                    predicted_match.start,
                    predicted_match.end,
                    predicted_match.canonical_term,
                )
            ] += 1
            span_predicted[(case.case_id, predicted_match.start, predicted_match.end)] += 1
            canonical_predicted[(case.case_id, predicted_match.canonical_term)] += 1
    return {
        "status": "available",
        "exact": _counter_metrics(exact_gold, exact_predicted),
        "span": _counter_metrics(span_gold, span_predicted),
        "canonical": _counter_metrics(canonical_gold, canonical_predicted),
    }


def _build_detector_report(
    run: DetectorRun,
    artifact: ArtifactMetadata,
    cases: Sequence[_GoldCase],
    predictions: Mapping[str, Prediction],
) -> dict[str, Any]:
    slice_names = sorted({slice_name for case in cases for slice_name in case.slices})
    slices = []
    for slice_name in slice_names:
        slice_cases = tuple(case for case in cases if slice_name in case.slices)
        slices.append(
            {
                "slice": slice_name,
                "case_count": len(slice_cases),
                "sentence_metrics": _sentence_metrics(slice_cases, predictions),
                "occurrence_metrics": _occurrence_metrics(
                    slice_cases, predictions, run.capabilities
                ),
            }
        )
    limitations = (
        []
        if run.capabilities.occurrences
        else ["detector does not expose occurrence spans or canonical terms"]
    )
    return {
        "detector_id": run.detector_id,
        "artifact": {
            "package": artifact.package,
            "version": artifact.version,
            "filename": artifact.filename,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
        },
        "profile": run.profile,
        "settings": dict(run.settings),
        "capabilities": {
            "sentence": run.capabilities.sentence,
            "occurrences": run.capabilities.occurrences,
            "spans": run.capabilities.spans,
            "canonical_terms": run.capabilities.canonical_terms,
        },
        "runtime": {
            "python_version": run.runtime.python_version,
            "implementation": run.runtime.implementation,
            "platform": run.runtime.platform,
            "dependencies": [
                {"package": package, "version": version}
                for package, version in run.runtime.dependencies
            ],
            "suppressed_output": run.runtime.suppressed_output,
        },
        "sentence_metrics": _sentence_metrics(cases, predictions),
        "occurrence_metrics": _occurrence_metrics(cases, predictions, run.capabilities),
        "slice_metrics": slices,
        "limitations": limitations,
    }


def _build_case_results(
    cases: Sequence[_GoldCase],
    runs: Sequence[DetectorRun],
    prediction_maps: Sequence[Mapping[str, Prediction]],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in cases:
        detector_results = []
        for run, predictions in zip(runs, prediction_maps, strict=True):
            prediction = predictions[case.case_id]
            item: dict[str, Any] = {
                "detector_id": run.detector_id,
                "detected": prediction.detected,
                "sentence_outcome": _sentence_outcome(bool(case.matches), prediction.detected),
                "predicted_occurrence_count": (
                    len(prediction.matches) if prediction.matches is not None else None
                ),
            }
            detector_results.append(item)
        results.append(
            {
                "case_id": case.case_id,
                "label": case.label,
                "slices": list(case.slices),
                "gold_detected": bool(case.matches),
                "gold_occurrence_count": len(case.matches),
                "detectors": detector_results,
            }
        )
    return results


def _invoke_worker(spec: DetectorSpec, case_inputs: Sequence[tuple[str, str]]) -> DetectorRun:
    worker_path = Path(__file__).with_name("detector_worker.py").resolve()
    request = {
        "protocol_version": _WORKER_PROTOCOL_VERSION,
        "detector_id": spec.detector_id,
        "package": spec.package,
        "version": spec.expected_version,
        "profile": spec.profile,
        "artifact_path": str(spec.artifact_path.resolve()),
        "artifact_sha256": _sha256_file(spec.artifact_path)[0],
        "cases": [{"case_id": case_id, "text": text} for case_id, text in case_inputs],
    }
    try:
        completed = subprocess.run(
            [str(spec.python_executable), "-I", "-X", "utf8", str(worker_path)],
            input=json.dumps(request, ensure_ascii=False).encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=_WORKER_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ComparisonError(f"{spec.detector_id} worker could not be executed") from exc
    try:
        response: object = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
        raise ComparisonError(f"{spec.detector_id} worker returned unsupported output") from exc
    if not isinstance(response, dict):
        raise ComparisonError(f"{spec.detector_id} worker returned unsupported output")
    payload = cast(dict[str, object], response)
    if completed.returncode != 0 or "error" in payload:
        error = payload.get("error")
        if isinstance(error, dict):
            stage = error.get("stage", "unknown")
            error_type = error.get("type", "WorkerError")
            if isinstance(stage, str) and isinstance(error_type, str):
                raise ComparisonError(
                    f"{spec.detector_id} worker failed during {stage} ({error_type})"
                )
        raise ComparisonError(f"{spec.detector_id} worker failed")
    return _parse_worker_run(payload, spec.detector_id)


def _parse_worker_run(payload: dict[str, object], detector_id: str) -> DetectorRun:
    try:
        if payload["protocol_version"] != _WORKER_PROTOCOL_VERSION:
            raise TypeError
        raw_capabilities = cast(dict[str, object], payload["capabilities"])
        capabilities = DetectorCapabilities(
            sentence=_require_bool(raw_capabilities["sentence"]),
            occurrences=_require_bool(raw_capabilities["occurrences"]),
            spans=_require_bool(raw_capabilities["spans"]),
            canonical_terms=_require_bool(raw_capabilities["canonical_terms"]),
        )
        raw_runtime = cast(dict[str, object], payload["runtime"])
        raw_dependencies = cast(list[object], raw_runtime["dependencies"])
        dependencies = tuple(
            (
                _require_str(cast(dict[str, object], item)["package"]),
                _require_str(cast(dict[str, object], item)["version"]),
            )
            for item in raw_dependencies
        )
        runtime = RuntimeMetadata(
            python_version=_require_str(raw_runtime["python_version"]),
            implementation=_require_str(raw_runtime["implementation"]),
            platform=_require_str(raw_runtime["platform"]),
            dependencies=dependencies,
            suppressed_output=_require_bool(raw_runtime["suppressed_output"]),
        )
        predictions = tuple(
            _parse_prediction(cast(dict[str, object], item), capabilities)
            for item in cast(list[object], payload["predictions"])
        )
        return DetectorRun(
            detector_id=_require_str(payload["detector_id"]),
            package=_require_str(payload["package"]),
            version=_require_str(payload["version"]),
            profile=_require_str(payload["profile"]),
            capabilities=capabilities,
            runtime=runtime,
            predictions=predictions,
            settings=_parse_settings(payload["settings"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ComparisonError(f"{detector_id} worker returned unsupported output") from exc


def _parse_prediction(payload: dict[str, object], capabilities: DetectorCapabilities) -> Prediction:
    raw_matches = payload["matches"]
    matches: tuple[PredictionMatch, ...] | None
    if raw_matches is None:
        matches = None
    else:
        matches = tuple(
            PredictionMatch(
                start=_require_int(cast(dict[str, object], item)["start"]),
                end=_require_int(cast(dict[str, object], item)["end"]),
                canonical_term=_require_str(cast(dict[str, object], item)["canonical_term"]),
            )
            for item in cast(list[object], raw_matches)
        )
    if capabilities.occurrences != (matches is not None):
        raise TypeError
    return Prediction(
        case_id=_require_str(payload["case_id"]),
        detected=_require_bool(payload["detected"]),
        matches=matches,
    )


def _parse_settings(payload: object) -> tuple[tuple[str, str | bool | int | float], ...]:
    if not isinstance(payload, dict):
        raise TypeError
    settings: list[tuple[str, str | bool | int | float]] = []
    for name, value in cast(dict[object, object], payload).items():
        if not isinstance(name, str) or not name:
            raise TypeError
        if isinstance(value, bool | str):
            settings.append((name, value))
        elif isinstance(value, int | float):
            settings.append((name, value))
        else:
            raise TypeError
    return tuple(sorted(settings))


def _require_str(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError
    return value


def _require_bool(value: object) -> bool:
    if type(value) is not bool:
        raise TypeError
    return value


def _require_int(value: object) -> int:
    if type(value) is not int:
        raise TypeError
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", nargs="+", required=True, type=Path)
    parser.add_argument("--koguard-wheel", required=True, type=Path)
    parser.add_argument("--korcen-wheel", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--koguard-python", type=Path, default=Path(sys.executable))
    parser.add_argument(
        "--koguard-profile",
        choices=KOGUARD_PROFILES,
        default=KOGUARD_PROFILE,
    )
    parser.add_argument("--korcen-python", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run both pinned artifacts and write a report without echoing corpus content."""

    arguments = _parser().parse_args(argv)
    try:
        specs = (
            make_koguard_spec(
                arguments.koguard_wheel,
                arguments.koguard_python,
                profile=arguments.koguard_profile,
            ),
            make_korcen_spec(arguments.korcen_wheel, arguments.korcen_python),
        )
        report = run_comparison(arguments.corpus, specs)
        arguments.output.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (ComparisonError, OSError, ValueError) as exc:
        print(f"comparison failed: {exc}", file=sys.stderr)
        return 1
    print(f"comparison report written: {arguments.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
