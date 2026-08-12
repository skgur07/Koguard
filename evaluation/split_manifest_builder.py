"""Build a versioned stable-ID split manifest from validated corpus files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from evaluation.corpus_validator import CorpusValidationError, validate_corpus_paths
from evaluation.split_guard import NORMALIZATION_VERSION


class SplitManifestBuildError(ValueError):
    """Raised when a manifest update could drop or silently move stable IDs."""


_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


def build_split_manifest(
    base_manifest_path: Path,
    corpus_paths: Sequence[Path],
    *,
    manifest_version: int,
    change_reason: str,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Build a manifest while preserving every existing stable assignment."""

    base = _read_object(base_manifest_path, "base split manifest")
    if (
        set(base)
        != {
            "schema_version",
            "manifest_id",
            "manifest_version",
            "change_reason",
            "normalization_version",
            "assignments",
        }
        or base.get("schema_version") != 1
    ):
        raise SplitManifestBuildError("base manifest violates version 1 contract")
    manifest_id = base.get("manifest_id")
    if not isinstance(manifest_id, str) or _ID_PATTERN.fullmatch(manifest_id) is None:
        raise SplitManifestBuildError("base manifest_id is invalid")
    if base.get("normalization_version") != NORMALIZATION_VERSION:
        raise SplitManifestBuildError("base normalization_version is incompatible")
    base_version = base.get("manifest_version")
    if type(base_version) is not int or manifest_version <= base_version:
        raise SplitManifestBuildError("manifest_version must exceed the base manifest version")
    if not change_reason.strip():
        raise SplitManifestBuildError("change_reason must not be empty")
    if len(change_reason) > 2000:
        raise SplitManifestBuildError("change_reason exceeds maximum length 2000")

    try:
        validate_corpus_paths(corpus_paths)
    except CorpusValidationError as exc:
        raise SplitManifestBuildError(str(exc)) from exc
    assignments = _load_assignments(corpus_paths)
    assignment_by_id = {assignment["case_id"]: assignment for assignment in assignments}
    base_assignments = base.get("assignments")
    if not isinstance(base_assignments, list):
        raise SplitManifestBuildError("base manifest assignments are invalid")
    for raw_assignment in base_assignments:
        if not isinstance(raw_assignment, dict):
            raise SplitManifestBuildError("base manifest assignment is invalid")
        assignment = cast(dict[str, Any], raw_assignment)
        case_id_value = assignment.get("case_id")
        if not isinstance(case_id_value, str):
            raise SplitManifestBuildError("base manifest case_id is invalid")
        case_id = case_id_value
        materialized = assignment_by_id.get(case_id)
        if materialized is None:
            raise SplitManifestBuildError(f"existing assignment is missing for case {case_id!r}")
        expected = {
            "case_id": case_id,
            "corpus_id": assignment.get("corpus_id"),
            "split": assignment.get("split"),
        }
        if materialized != expected:
            raise SplitManifestBuildError(f"existing assignment moved for case {case_id!r}")

    manifest: dict[str, Any] = {
        "schema_version": 1,
        "manifest_id": manifest_id,
        "manifest_version": manifest_version,
        "change_reason": change_reason,
        "normalization_version": NORMALIZATION_VERSION,
        "assignments": assignments,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return manifest


def _read_object(path: Path, description: str) -> dict[str, Any]:
    try:
        payload: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SplitManifestBuildError(f"failed to read {description}") from exc
    if not isinstance(payload, dict):
        raise SplitManifestBuildError(f"{description} root must be an object")
    return cast(dict[str, Any], payload)


def _discover_corpus_files(paths: Sequence[Path]) -> tuple[Path, ...]:
    discovered: set[Path] = set()
    for raw_path in paths:
        path = raw_path.resolve()
        if path.is_dir():
            discovered.update(candidate.resolve() for candidate in path.rglob("*.json"))
        elif path.is_file():
            discovered.add(path)
    return tuple(sorted(discovered, key=lambda item: item.as_posix()))


def _load_assignments(paths: Sequence[Path]) -> list[dict[str, str]]:
    assignments: list[dict[str, str]] = []
    for path in _discover_corpus_files(paths):
        corpus = _read_object(path, "corpus")
        corpus_id = cast(str, corpus["corpus_id"])
        for raw_case in cast(list[dict[str, Any]], corpus["cases"]):
            assignments.append(
                {
                    "case_id": cast(str, raw_case["id"]),
                    "corpus_id": corpus_id,
                    "split": cast(str, raw_case["split"]),
                }
            )
    return sorted(assignments, key=lambda item: item["case_id"])


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_manifest", type=Path)
    parser.add_argument("corpus", nargs="+", type=Path)
    parser.add_argument("--manifest-version", required=True, type=int)
    parser.add_argument("--change-reason", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write a new manifest and report non-sensitive assignment counts."""

    arguments = _parser().parse_args(argv)
    try:
        manifest = build_split_manifest(
            arguments.base_manifest,
            arguments.corpus,
            manifest_version=arguments.manifest_version,
            change_reason=arguments.change_reason,
            output_path=arguments.output,
        )
    except SplitManifestBuildError as exc:
        print(f"split manifest build failed: {exc}", file=sys.stderr)
        return 1
    assignments = cast(list[Mapping[str, str]], manifest["assignments"])
    split_counts = {
        split: sum(assignment["split"] == split for assignment in assignments)
        for split in ("regression", "tuning", "evaluation", "private")
    }
    counts = ", ".join(f"{split}={count}" for split, count in split_counts.items() if count)
    print(
        f"manifest={manifest['manifest_id']}@{manifest['manifest_version']}; "
        f"assignments={len(assignments)}; {counts}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
