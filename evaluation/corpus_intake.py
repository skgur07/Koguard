"""Build deterministic review-only intake from a license-pinned external corpus."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

SOURCE_SPEC_SCHEMA_PATH = Path(__file__).with_name("corpus-source.schema.json")
INTAKE_REPORT_SCHEMA_PATH = Path(__file__).with_name("corpus-intake-report.schema.json")
DEFAULT_SOURCE_SPEC_PATH = Path(__file__).with_name("sources") / "curse-detection-data.v1.json"
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_SENSITIVE_PATTERN = re.compile(
    r"(?:https?://|www\.|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"(?<!\d)01[016789][ -]?\d{3,4}[ -]?\d{4}(?!\d)|"
    r"(?<!\d)\d{6}[ -]?\d{7}(?!\d)|"
    r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?!\d)|"
    r"(?<!\d)\d{6,}(?!\d)|"
    r"(?<!\w)@[A-Z0-9_]{2,})",
    re.IGNORECASE,
)


class CorpusIntakeError(ValueError):
    """Raised when source provenance or intake invariants fail."""


@dataclass(frozen=True, slots=True)
class CorpusIntakeResult:
    """Generated corpus and non-sensitive provenance report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _SourceRow:
    row_number: int
    text: str
    source_label: str
    identity: str
    rank: str


def build_review_intake(
    source_spec_path: Path,
    artifact_path: Path,
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> CorpusIntakeResult:
    """Validate a pinned artifact and select a deterministic unadjudicated review queue."""

    spec = _load_spec(source_spec_path)
    content = _read_artifact(artifact_path)
    actual_sha256 = hashlib.sha256(content).hexdigest()
    artifact = cast(dict[str, Any], spec["artifact"])
    if actual_sha256 != artifact["sha256"]:
        raise CorpusIntakeError("artifact SHA-256 mismatch")
    if len(content) != artifact["size_bytes"]:
        raise CorpusIntakeError("artifact byte size mismatch")

    rows = _parse_rows(content, spec)
    if len(rows) != artifact["line_count"]:
        raise CorpusIntakeError("artifact line count mismatch")
    eligible_rows = tuple(row for row in rows if _SENSITIVE_PATTERN.search(row.text) is None)
    intake = cast(dict[str, Any], spec["intake"])
    target_by_label = cast(dict[str, int], intake["target_by_source_label"])
    selected = _select_rows(eligible_rows, target_by_label)
    corpus = _build_corpus(spec, selected)
    source_counts = Counter(row.source_label for row in rows)
    eligible_counts = Counter(row.source_label for row in eligible_rows)
    selected_counts = Counter(row.source_label for row in selected)
    report: dict[str, Any] = {
        "schema_version": 1,
        "source_id": spec["source_id"],
        "source_revision": spec["revision"],
        "artifact_sha256": actual_sha256,
        "source_row_count": len(rows),
        "source_label_counts": {label: source_counts[label] for label in ("0", "1")},
        "sensitive_pattern_excluded_count": len(rows) - len(eligible_rows),
        "eligible_source_label_counts": {label: eligible_counts[label] for label in ("0", "1")},
        "selected_count": len(selected),
        "selected_source_label_counts": {label: selected_counts[label] for label in ("0", "1")},
        "generated_label_counts": {
            "positive": 0,
            "hard-negative": 0,
            "review": len(selected),
        },
        "source_statistics": [
            {
                "source_id": spec["source_id"],
                "selected_count": len(selected),
                "share": 1.0,
            }
        ],
        "slice_counts": {"unadjudicated-intake": len(selected)},
        "adjudication_quality": {
            "adjudicated": 0,
            "single_review": 0,
            "double_review": 0,
            "disagreement": 0,
            "pending_review": len(selected),
        },
        "bias_findings": [
            "One source supplies 100% of this intake; add at least two independent sources "
            "and curated negative slices before gold evaluation."
        ],
        "gold_ready": False,
        "completion_blockers": [
            f"{len(selected)} review cases still require Koguard-policy "
            "adjudication and exact spans.",
            "Automated sensitive-pattern exclusion still requires manual privacy review.",
            "Independent hidden evaluation material is not part of this public intake.",
        ],
    }
    result = CorpusIntakeResult(corpus, report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _load_spec(path: Path) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CorpusIntakeError("failed to read source specification") from exc
    if not isinstance(payload, dict):
        raise CorpusIntakeError("source specification root must be an object")
    spec = cast(dict[str, Any], payload)
    required = {
        "schema_version",
        "source_id",
        "repository",
        "revision",
        "artifact",
        "license",
        "format",
        "intake",
    }
    if set(spec) != required or spec.get("schema_version") != 1:
        raise CorpusIntakeError("source specification violates version 1 contract")
    source_id = spec.get("source_id")
    repository = spec.get("repository")
    revision = spec.get("revision")
    if not isinstance(source_id, str) or _ID_PATTERN.fullmatch(source_id) is None:
        raise CorpusIntakeError("source_id is invalid")
    if not isinstance(repository, str) or not repository.startswith("https://"):
        raise CorpusIntakeError("source repository is invalid")
    if not isinstance(revision, str) or not revision or len(revision) > 200:
        raise CorpusIntakeError("source revision is invalid")
    artifact_data = spec.get("artifact")
    if not isinstance(artifact_data, dict) or set(artifact_data) != {
        "url",
        "sha256",
        "size_bytes",
        "line_count",
    }:
        raise CorpusIntakeError("artifact configuration is invalid")
    artifact_url = artifact_data.get("url")
    artifact_sha256 = artifact_data.get("sha256")
    artifact_size = artifact_data.get("size_bytes")
    artifact_lines = artifact_data.get("line_count")
    if not isinstance(artifact_url, str) or not artifact_url.startswith("https://"):
        raise CorpusIntakeError("artifact URL is invalid")
    if not isinstance(artifact_sha256, str) or _SHA256_PATTERN.fullmatch(artifact_sha256) is None:
        raise CorpusIntakeError("artifact SHA-256 is invalid")
    if type(artifact_size) is not int or artifact_size < 1:
        raise CorpusIntakeError("artifact size is invalid")
    if type(artifact_lines) is not int or artifact_lines < 1:
        raise CorpusIntakeError("artifact line count is invalid")
    license_data = spec.get("license")
    if not isinstance(license_data, dict) or set(license_data) != {
        "spdx",
        "url",
        "sha256",
        "redistribution_allowed",
    }:
        raise CorpusIntakeError("source license is invalid")
    if license_data.get("spdx") != "MIT" or license_data.get("redistribution_allowed") is not True:
        raise CorpusIntakeError("source license is not approved for redistribution")
    license_url = license_data.get("url")
    license_sha256 = license_data.get("sha256")
    if not isinstance(license_url, str) or not license_url.startswith("https://"):
        raise CorpusIntakeError("source license URL is invalid")
    if not isinstance(license_sha256, str) or _SHA256_PATTERN.fullmatch(license_sha256) is None:
        raise CorpusIntakeError("source license SHA-256 is invalid")
    format_data = spec.get("format")
    if not isinstance(format_data, dict) or format_data != {
        "delimiter": "|",
        "text_column": 0,
        "label_column": 1,
        "allowed_labels": ["0", "1"],
    }:
        raise CorpusIntakeError("source format is unsupported")
    intake = spec.get("intake")
    if not isinstance(intake, dict) or set(intake) != {
        "corpus_id",
        "split",
        "selection",
        "target_by_source_label",
    }:
        raise CorpusIntakeError("intake configuration is invalid")
    corpus_id = intake.get("corpus_id")
    if not isinstance(corpus_id, str) or _ID_PATTERN.fullmatch(corpus_id) is None:
        raise CorpusIntakeError("intake corpus_id is invalid")
    if intake.get("split") != "tuning" or intake.get("selection") != "stable-sha256-rank-v1":
        raise CorpusIntakeError("intake policy is unsupported")
    targets = intake.get("target_by_source_label")
    if (
        not isinstance(targets, dict)
        or set(targets) != {"0", "1"}
        or any(type(value) is not int or value < 0 for value in targets.values())
        or sum(cast(dict[str, int], targets).values()) < 1
    ):
        raise CorpusIntakeError("target_by_source_label is invalid")
    return spec


def _read_artifact(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CorpusIntakeError("failed to read source artifact") from exc


def _parse_rows(content: bytes, spec: Mapping[str, Any]) -> tuple[_SourceRow, ...]:
    try:
        lines = content.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError as exc:
        raise CorpusIntakeError("source artifact must be UTF-8") from exc
    source_id = cast(str, spec["source_id"])
    revision = cast(str, spec["revision"])
    rows: list[_SourceRow] = []
    seen_identity: set[str] = set()
    for row_number, line in enumerate(lines, start=1):
        try:
            text, source_label = line.rsplit("|", 1)
        except ValueError as exc:
            raise CorpusIntakeError(f"source row {row_number} has invalid format") from exc
        if not text or source_label not in {"0", "1"}:
            raise CorpusIntakeError(f"source row {row_number} has invalid fields")
        if len(text) > 4096:
            raise CorpusIntakeError(f"source row {row_number} exceeds maximum text length")
        identity = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if identity in seen_identity:
            raise CorpusIntakeError(f"source row {row_number} duplicates an earlier text")
        seen_identity.add(identity)
        rank_payload = f"{source_id}\0{revision}\0{source_label}\0{identity}".encode()
        rows.append(
            _SourceRow(
                row_number=row_number,
                text=text,
                source_label=source_label,
                identity=identity,
                rank=hashlib.sha256(rank_payload).hexdigest(),
            )
        )
    return tuple(rows)


def _select_rows(
    rows: Sequence[_SourceRow],
    target_by_label: Mapping[str, int],
) -> tuple[_SourceRow, ...]:
    by_label: dict[str, list[_SourceRow]] = defaultdict(list)
    for row in rows:
        by_label[row.source_label].append(row)
    selected: list[_SourceRow] = []
    for label in ("0", "1"):
        available = by_label[label]
        target = target_by_label[label]
        if len(available) < target:
            raise CorpusIntakeError(
                f"source label {label!r} has {len(available)} rows; {target} required"
            )
        selected.extend(sorted(available, key=lambda row: (row.rank, row.row_number))[:target])
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
                    "name": "2runo/Curse-detection-data",
                    "reference": repository,
                    "revision": revision,
                    "redistribution_allowed": True,
                },
                "license": "MIT",
                "split": "tuning",
                "notes": "Unadjudicated intake; external annotation is not Koguard gold.",
            }
            for row in rows
        ],
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_spec", type=Path)
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the review intake and print aggregate counts only."""

    arguments = _parser().parse_args(argv)
    try:
        result = build_review_intake(
            arguments.source_spec,
            arguments.artifact,
            output_path=arguments.output,
            report_path=arguments.report,
        )
    except CorpusIntakeError as exc:
        print(f"corpus intake failed: {exc}", file=sys.stderr)
        return 1
    report = result.report
    print(
        f"rows={report['source_row_count']}; selected={report['selected_count']}; "
        f"gold_ready={str(report['gold_ready']).lower()}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
