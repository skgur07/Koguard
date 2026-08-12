"""Build a non-redistributable review queue from a rights-pending composite source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_intake import _SENSITIVE_PATTERN
from evaluation.split_guard import _normalize_for_leak_check

QUARANTINE_SOURCE_SCHEMA_PATH = Path(__file__).with_name("quarantine-source.schema.json")
QUARANTINE_REPORT_SCHEMA_PATH = Path(__file__).with_name("quarantine-report.schema.json")
DEFAULT_QUARANTINE_SOURCE_PATH = (
    Path(__file__).with_name("sources") / "candidates" / "zizun-korean-malicious-comments.v1.json"
)
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SPEC_FIELDS = frozenset(
    {
        "schema_version",
        "source_id",
        "repository",
        "revision",
        "artifacts",
        "format",
        "components",
        "rights_review",
        "exclusions",
        "intake",
    }
)
_ARTIFACT_FIELDS = frozenset({"url", "sha256", "size_bytes"})
_DATASET_ARTIFACT_FIELDS = _ARTIFACT_FIELDS | {"row_count"}


class QuarantineIntakeError(ValueError):
    """Raised when a pending-rights source violates its quarantine contract."""


@dataclass(frozen=True, slots=True)
class QuarantineIntakeResult:
    """Generated local-only corpus and non-sensitive audit report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _SourceRow:
    row_number: int
    text: str
    source_label: str
    identity: str
    normalized: str
    rank: str


def build_quarantine_intake(
    source_spec_path: Path,
    dataset_path: Path,
    license_path: Path,
    provenance_path: Path,
    exclusion_paths: Sequence[Path],
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> QuarantineIntakeResult:
    """Verify, deduplicate, and select a local-only review queue."""

    _validate_output_paths(
        (source_spec_path, dataset_path, license_path, provenance_path, *exclusion_paths),
        output_path=output_path,
        report_path=report_path,
    )
    spec = _load_spec(source_spec_path)
    artifacts = cast(dict[str, dict[str, Any]], spec["artifacts"])
    dataset_content = _verify_artifact("dataset", dataset_path, artifacts["dataset"])
    _verify_artifact("license", license_path, artifacts["license"])
    _verify_artifact("provenance", provenance_path, artifacts["provenance"])
    rows, all_texts, source_label_counts = _parse_dataset(dataset_content, spec)
    expected_row_count = cast(int, artifacts["dataset"]["row_count"])
    if sum(source_label_counts.values()) != expected_row_count:
        raise QuarantineIntakeError("dataset row count mismatch")

    exclusions = cast(list[dict[str, Any]], spec["exclusions"])
    if len(exclusion_paths) != len(exclusions):
        raise QuarantineIntakeError("exclusion path count does not match source specification")
    excluded_texts: set[str] = set()
    for exclusion_path, exclusion in zip(exclusion_paths, exclusions, strict=True):
        content = _read_bytes(exclusion_path, "exclusion artifact")
        if hashlib.sha256(content).hexdigest() != exclusion["artifact_sha256"]:
            raise QuarantineIntakeError("exclusion artifact SHA-256 mismatch")
        excluded_texts.update(_parse_pipe_last_label(content))
    excluded_normalized = {_normalize_for_leak_check(text) for text in excluded_texts}
    row_texts = {row.text for row in rows}
    row_normalized = {row.normalized for row in rows}
    direct_overlap = len(row_texts & excluded_texts)
    normalized_overlap = len(row_normalized & excluded_normalized)

    non_overlapping = [row for row in rows if row.normalized not in excluded_normalized]
    non_sensitive = [row for row in non_overlapping if _SENSITIVE_PATTERN.search(row.text) is None]
    sensitive_excluded = len(non_overlapping) - len(non_sensitive)
    deduplicated, duplicate_excluded, conflicting_groups = _deduplicate_rows(non_sensitive)
    eligible_counts = Counter(row.source_label for row in deduplicated)
    intake = cast(dict[str, Any], spec["intake"])
    targets = cast(dict[str, int], intake["target_by_source_label"])
    selected = _select_rows(deduplicated, targets)
    selected_counts = Counter(row.source_label for row in selected)
    corpus = _build_corpus(spec, selected)
    rights_review = cast(dict[str, Any], spec["rights_review"])
    report: dict[str, Any] = {
        "schema_version": 1,
        "source_id": spec["source_id"],
        "source_revision": spec["revision"],
        "artifact_sha256": artifacts["dataset"]["sha256"],
        "source_row_count": expected_row_count,
        "source_label_counts": {
            "0": source_label_counts["0"],
            "1": source_label_counts["1"],
            "missing": source_label_counts["missing"],
        },
        "exact_unique_text_count": len(set(all_texts)),
        "normalized_unique_text_count": len(
            {_normalize_for_leak_check(text) for text in all_texts}
        ),
        "direct_overlap_excluded": direct_overlap,
        "normalized_overlap_excluded": normalized_overlap,
        "sensitive_pattern_excluded": sensitive_excluded,
        "normalized_duplicate_excluded": duplicate_excluded,
        "conflicting_duplicate_groups": conflicting_groups,
        "eligible_source_label_counts": {
            "0": eligible_counts["0"],
            "1": eligible_counts["1"],
        },
        "selected_count": len(selected),
        "selected_source_label_counts": {
            "0": selected_counts["0"],
            "1": selected_counts["1"],
        },
        "generated_label_counts": {
            "positive": 0,
            "hard-negative": 0,
            "review": len(selected),
        },
        "rights_review_status": "pending",
        "redistribution_allowed": False,
        "independent_source_ready": False,
        "gold_ready": False,
        "completion_blockers": list(cast(list[str], rights_review["blockers"])),
    }
    result = QuarantineIntakeResult(corpus, report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _load_spec(path: Path) -> dict[str, Any]:
    spec = _read_object(path, "quarantine source specification")
    if set(spec) != _SPEC_FIELDS or spec.get("schema_version") != 1:
        raise QuarantineIntakeError("source specification violates version 1 contract")
    _require_identifier(spec.get("source_id"), "source_id")
    repository = spec.get("repository")
    revision = spec.get("revision")
    if not isinstance(repository, str) or not repository.startswith("https://"):
        raise QuarantineIntakeError("source repository is invalid")
    if not isinstance(revision, str) or not revision or len(revision) > 200:
        raise QuarantineIntakeError("source revision is invalid")
    artifacts = spec.get("artifacts")
    if not isinstance(artifacts, dict) or set(artifacts) != {
        "dataset",
        "license",
        "provenance",
    }:
        raise QuarantineIntakeError("source artifacts configuration is invalid")
    for name in ("dataset", "license", "provenance"):
        artifact = artifacts.get(name)
        required_fields = _DATASET_ARTIFACT_FIELDS if name == "dataset" else _ARTIFACT_FIELDS
        _validate_artifact_config(name, artifact, required_fields)
    if spec.get("format") != {
        "kind": "tsv-header",
        "text_column": "content",
        "label_column": "lable",
        "allowed_labels": ["0", "1"],
    }:
        raise QuarantineIntakeError("source format is unsupported")
    _validate_components(spec.get("components"))
    _validate_rights_review(spec.get("rights_review"))
    _validate_exclusions(spec.get("exclusions"))
    _validate_intake(spec.get("intake"))
    return spec


def _validate_artifact_config(name: str, payload: object, required: frozenset[str]) -> None:
    if not isinstance(payload, dict) or set(payload) != required:
        raise QuarantineIntakeError(f"{name} artifact configuration is invalid")
    url = payload.get("url")
    sha256 = payload.get("sha256")
    size_bytes = payload.get("size_bytes")
    if not isinstance(url, str) or not url.startswith("https://"):
        raise QuarantineIntakeError(f"{name} artifact URL is invalid")
    if not isinstance(sha256, str) or _SHA256_PATTERN.fullmatch(sha256) is None:
        raise QuarantineIntakeError(f"{name} artifact SHA-256 is invalid")
    if type(size_bytes) is not int or size_bytes < 1:
        raise QuarantineIntakeError(f"{name} artifact size is invalid")
    if name == "dataset":
        row_count = payload.get("row_count")
        if type(row_count) is not int or row_count < 1:
            raise QuarantineIntakeError("dataset artifact row count is invalid")


def _validate_components(payload: object) -> None:
    if not isinstance(payload, list) or not payload:
        raise QuarantineIntakeError("components must be a non-empty array")
    required = {"source_id", "reference", "declared_license", "stated_row_count"}
    for component in payload:
        if not isinstance(component, dict) or set(component) != required:
            raise QuarantineIntakeError("component configuration is invalid")
        _require_identifier(component.get("source_id"), "component source_id")
        if not isinstance(component.get("reference"), str) or not component["reference"].startswith(
            "https://"
        ):
            raise QuarantineIntakeError("component reference is invalid")
        license_name = component.get("declared_license")
        if not isinstance(license_name, str) or not license_name or len(license_name) > 128:
            raise QuarantineIntakeError("component declared_license is invalid")
        row_count = component.get("stated_row_count")
        if type(row_count) is not int or row_count < 1:
            raise QuarantineIntakeError("component stated_row_count is invalid")


def _validate_rights_review(payload: object) -> None:
    required = {"status", "redistribution_allowed", "allowed_scope", "blockers"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise QuarantineIntakeError("rights_review configuration is invalid")
    if payload.get("status") != "pending" or payload.get("redistribution_allowed") is not False:
        raise QuarantineIntakeError("rights_review must remain non-redistributable and pending")
    if payload.get("allowed_scope") != "local-quarantine-analysis-only":
        raise QuarantineIntakeError("rights_review allowed_scope is invalid")
    blockers = payload.get("blockers")
    if (
        not isinstance(blockers, list)
        or not blockers
        or any(not isinstance(item, str) or not item or len(item) > 500 for item in blockers)
    ):
        raise QuarantineIntakeError("rights_review blockers are invalid")


def _validate_exclusions(payload: object) -> None:
    required = {"source_id", "artifact_sha256", "format"}
    if not isinstance(payload, list) or not payload:
        raise QuarantineIntakeError("exclusions must be a non-empty array")
    for exclusion in payload:
        if not isinstance(exclusion, dict) or set(exclusion) != required:
            raise QuarantineIntakeError("exclusion configuration is invalid")
        _require_identifier(exclusion.get("source_id"), "exclusion source_id")
        sha256 = exclusion.get("artifact_sha256")
        if not isinstance(sha256, str) or _SHA256_PATTERN.fullmatch(sha256) is None:
            raise QuarantineIntakeError("exclusion artifact SHA-256 is invalid")
        if exclusion.get("format") != "pipe-last-label":
            raise QuarantineIntakeError("exclusion format is unsupported")


def _validate_intake(payload: object) -> None:
    required = {"corpus_id", "split", "selection", "target_by_source_label"}
    if not isinstance(payload, dict) or set(payload) != required:
        raise QuarantineIntakeError("intake configuration is invalid")
    _require_identifier(payload.get("corpus_id"), "intake corpus_id")
    if payload.get("split") != "tuning" or payload.get("selection") != "stable-sha256-rank-v1":
        raise QuarantineIntakeError("intake policy is unsupported")
    targets = payload.get("target_by_source_label")
    if (
        not isinstance(targets, dict)
        or set(targets) != {"0", "1"}
        or any(type(value) is not int or value < 0 for value in targets.values())
        or sum(cast(dict[str, int], targets).values()) < 1
    ):
        raise QuarantineIntakeError("target_by_source_label is invalid")


def _verify_artifact(name: str, path: Path, config: Mapping[str, Any]) -> bytes:
    content = _read_bytes(path, f"{name} artifact")
    if hashlib.sha256(content).hexdigest() != config["sha256"]:
        raise QuarantineIntakeError(f"{name} SHA-256 mismatch")
    if len(content) != config["size_bytes"]:
        raise QuarantineIntakeError(f"{name} byte size mismatch")
    return content


def _parse_dataset(
    content: bytes,
    spec: Mapping[str, Any],
) -> tuple[list[_SourceRow], list[str], Counter[str]]:
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise QuarantineIntakeError("dataset must be UTF-8") from exc
    reader = csv.DictReader(io.StringIO(decoded, newline=""), delimiter="\t")
    if reader.fieldnames != ["content", "lable"]:
        raise QuarantineIntakeError("dataset header is invalid")
    source_id = cast(str, spec["source_id"])
    revision = cast(str, spec["revision"])
    rows: list[_SourceRow] = []
    all_texts: list[str] = []
    label_counts: Counter[str] = Counter()
    raw_row_count = 0
    for row_number, row in enumerate(reader, start=1):
        raw_row_count += 1
        text = row.get("content")
        label = row.get("lable")
        if not isinstance(text, str) or not text or len(text) > 4096 or not _is_valid_utf8(text):
            raise QuarantineIntakeError(f"dataset row {row_number} text is invalid")
        all_texts.append(text)
        if label not in {"0", "1"}:
            label_counts["missing"] += 1
            continue
        label_counts[label] += 1
        identity = hashlib.sha256(text.encode("utf-8")).hexdigest()
        rank_payload = f"{source_id}\0{revision}\0{label}\0{identity}".encode()
        rows.append(
            _SourceRow(
                row_number=row_number,
                text=text,
                source_label=label,
                identity=identity,
                normalized=_normalize_for_leak_check(text),
                rank=hashlib.sha256(rank_payload).hexdigest(),
            )
        )
    expected_row_count = cast(dict[str, Any], spec["artifacts"])["dataset"]["row_count"]
    if raw_row_count != expected_row_count:
        raise QuarantineIntakeError("dataset row count mismatch")
    return rows, all_texts, label_counts


def _parse_pipe_last_label(content: bytes) -> set[str]:
    try:
        lines = content.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise QuarantineIntakeError("exclusion artifact must be UTF-8") from exc
    texts: set[str] = set()
    for row_number, line in enumerate(lines, start=1):
        try:
            text, label = line.rsplit("|", 1)
        except ValueError as exc:
            raise QuarantineIntakeError(
                f"exclusion artifact row {row_number} has invalid format"
            ) from exc
        if not text or label not in {"0", "1"}:
            raise QuarantineIntakeError(f"exclusion artifact row {row_number} has invalid fields")
        texts.add(text)
    return texts


def _deduplicate_rows(rows: Sequence[_SourceRow]) -> tuple[list[_SourceRow], int, int]:
    by_normalized: dict[str, list[_SourceRow]] = defaultdict(list)
    for row in rows:
        by_normalized[row.normalized].append(row)
    retained: list[_SourceRow] = []
    duplicate_excluded = 0
    conflicting_groups = 0
    for group in by_normalized.values():
        labels = {row.source_label for row in group}
        if len(labels) > 1:
            conflicting_groups += 1
            duplicate_excluded += len(group)
            continue
        ordered = sorted(group, key=lambda row: (row.rank, row.row_number))
        retained.append(ordered[0])
        duplicate_excluded += len(ordered) - 1
    return retained, duplicate_excluded, conflicting_groups


def _select_rows(rows: Sequence[_SourceRow], targets: Mapping[str, int]) -> tuple[_SourceRow, ...]:
    by_label: dict[str, list[_SourceRow]] = defaultdict(list)
    for row in rows:
        by_label[row.source_label].append(row)
    selected: list[_SourceRow] = []
    for label in ("0", "1"):
        available = sorted(by_label[label], key=lambda row: (row.rank, row.row_number))
        target = targets[label]
        if len(available) < target:
            raise QuarantineIntakeError(
                f"source label {label!r} has {len(available)} eligible rows; {target} required"
            )
        selected.extend(available[:target])
    return tuple(sorted(selected, key=lambda row: (row.source_label, row.rank, row.row_number)))


def _build_corpus(spec: Mapping[str, Any], rows: Sequence[_SourceRow]) -> dict[str, Any]:
    source_id = cast(str, spec["source_id"])
    repository = cast(str, spec["repository"])
    revision = cast(str, spec["revision"])
    intake = cast(dict[str, Any], spec["intake"])
    return {
        "schema_version": 1,
        "corpus_id": intake["corpus_id"],
        "cases": [
            {
                "id": f"{source_id}-review-{row.identity[:20]}",
                "text": row.text,
                "label": "review",
                "expected_matches": [],
                "slices": ["unadjudicated-intake"],
                "source": {
                    "kind": "licensed",
                    "name": source_id,
                    "reference": repository,
                    "revision": revision,
                    "redistribution_allowed": False,
                },
                "license": "LicenseRef-PendingReview",
                "split": "tuning",
                "notes": (
                    "Local quarantine intake; upstream label and composite provenance are not "
                    "Koguard gold; rights review pending."
                ),
            }
            for row in rows
        ],
    }


def _validate_output_paths(
    input_paths: Sequence[Path],
    *,
    output_path: Path | None,
    report_path: Path | None,
) -> None:
    resolved_inputs = {path.resolve() for path in input_paths}
    if output_path is not None and output_path.resolve() in resolved_inputs:
        raise QuarantineIntakeError("output must not overwrite an input")
    if report_path is not None and report_path.resolve() in resolved_inputs:
        raise QuarantineIntakeError("output must not overwrite an input")
    if (
        output_path is not None
        and report_path is not None
        and output_path.resolve() == report_path.resolve()
    ):
        raise QuarantineIntakeError("output and report paths must differ")


def _require_identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _ID_PATTERN.fullmatch(value) is None:
        raise QuarantineIntakeError(f"{name} is invalid")
    return value


def _is_valid_utf8(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _read_bytes(path: Path, description: str) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise QuarantineIntakeError(f"failed to read {description}") from exc


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise QuarantineIntakeError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise QuarantineIntakeError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as exc:
        raise QuarantineIntakeError("failed to write JSON output") from exc


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_spec", type=Path)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("license", type=Path)
    parser.add_argument("provenance", type=Path)
    parser.add_argument("--exclusion", action="append", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Create a quarantine queue and print aggregate counts only."""

    arguments = _parser().parse_args(argv)
    try:
        result = build_quarantine_intake(
            arguments.source_spec,
            arguments.dataset,
            arguments.license,
            arguments.provenance,
            arguments.exclusion,
            output_path=arguments.output,
            report_path=arguments.report,
        )
    except QuarantineIntakeError as exc:
        print(f"quarantine intake failed: {exc}", file=sys.stderr)
        return 1
    report = result.report
    print(
        f"rows={report['source_row_count']}; selected={report['selected_count']}; "
        f"rights={report['rights_review_status']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
