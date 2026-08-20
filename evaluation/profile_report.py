"""Build a privacy-safe public profile report from a protected ablation report."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from koguard import KoguardEngine, ProfileName

PROFILE_REPORT_SCHEMA_PATH = Path(__file__).with_name("profile-report.schema.json")
DEFAULT_OUTPUT_PATH = Path(__file__).with_name("results") / "pf009-profile-evaluation.report.json"

_SOURCE_PROFILE_IDS: tuple[tuple[ProfileName, str], ...] = (
    ("strict", "exact-alias"),
    ("balanced", "choseong"),
    ("aggressive", "all-enabled"),
)
_NORMAL_FP_RATE_LIMIT = 0.005
_SHORT_CHAT_P95_LIMIT_MS = 1.0
_MAXIMUM_INPUT_P95_LIMIT_MS = 15.0


class ProfileReportError(ValueError):
    """Raised when a protected ablation report cannot produce the public report."""


def _object(value: object, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProfileReportError(f"{label} must be an object")
    return cast(dict[str, Any], value)


def _integer(value: object, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ProfileReportError(f"{label} must be a non-negative integer")
    return value


def _number(value: object, label: str) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ProfileReportError(f"{label} must be a non-negative number")
    return float(value)


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProfileReportError(f"{label} must be a non-empty string")
    return value


def _optional_number(value: object, label: str) -> float | None:
    if value is None:
        return None
    return _number(value, label)


def _config_settings(profile: ProfileName) -> dict[str, str | bool | int | float]:
    config = KoguardEngine(profile=profile).config
    return {
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


def _source_profiles(source: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    raw_profiles = source.get("profiles")
    if not isinstance(raw_profiles, list):
        raise ProfileReportError("profiles must be an array")
    profiles: dict[str, dict[str, Any]] = {}
    for raw_profile in raw_profiles:
        profile = _object(raw_profile, "profile")
        profile_id = profile.get("profile_id")
        if isinstance(profile_id, str):
            if profile_id in profiles:
                raise ProfileReportError(f"duplicate source profile: {profile_id}")
            profiles[profile_id] = profile
    return profiles


def _sanitized_metrics(value: object, label: str, *, sentence: bool) -> dict[str, Any]:
    metrics = _object(value, label)
    counts = _object(metrics.get("counts"), f"{label}.counts")
    sanitized_counts = {
        key: _integer(counts.get(key), f"{label}.counts.{key}") for key in ("tp", "fp", "fn")
    }
    if sentence:
        sanitized_counts["tn"] = _integer(counts.get("tn"), f"{label}.counts.tn")
    sanitized = {
        "counts": sanitized_counts,
        "precision": _optional_number(metrics.get("precision"), f"{label}.precision"),
        "recall": _optional_number(metrics.get("recall"), f"{label}.recall"),
        "f1": _optional_number(metrics.get("f1"), f"{label}.f1"),
    }
    if sentence:
        sanitized["accuracy"] = _optional_number(metrics.get("accuracy"), f"{label}.accuracy")
    return sanitized


def _sanitized_performance(value: object, label: str) -> dict[str, Any]:
    performance = _object(value, label)
    workloads: dict[str, dict[str, int | float]] = {}
    for workload_id in ("short_chat", "maximum_input"):
        workload = _object(performance.get(workload_id), f"{label}.{workload_id}")
        workloads[workload_id] = {
            "input_length": _integer(
                workload.get("input_length"), f"{label}.{workload_id}.input_length"
            ),
            "p50_ms": _number(workload.get("p50_ms"), f"{label}.{workload_id}.p50_ms"),
            "p95_ms": _number(workload.get("p95_ms"), f"{label}.{workload_id}.p95_ms"),
        }
    return {
        **workloads,
        "engine_retained_memory_bytes": _integer(
            performance.get("engine_retained_memory_bytes"),
            f"{label}.engine_retained_memory_bytes",
        ),
    }


def _validated_profile(
    profile: ProfileName,
    source_profile_id: str,
    source_profiles: Mapping[str, dict[str, Any]],
) -> dict[str, Any]:
    try:
        source = source_profiles[source_profile_id]
    except KeyError as exc:
        raise ProfileReportError(f"missing source profile: {source_profile_id}") from exc
    settings = _object(source.get("settings"), f"{source_profile_id}.settings")
    if settings != _config_settings(profile):
        raise ProfileReportError(
            f"source profile {source_profile_id} does not match public profile {profile}"
        )
    sentence = _sanitized_metrics(
        source.get("sentence_metrics"),
        f"{source_profile_id}.sentence_metrics",
        sentence=True,
    )
    occurrence = _sanitized_metrics(
        source.get("occurrence_metrics"),
        f"{source_profile_id}.occurrence_metrics",
        sentence=False,
    )
    performance = _sanitized_performance(
        source.get("performance"), f"{source_profile_id}.performance"
    )
    return {
        "profile": profile,
        "source_profile_id": source_profile_id,
        "settings": copy.deepcopy(settings),
        "sentence_metrics": sentence,
        "occurrence_metrics": occurrence,
        "performance": performance,
    }


def _metric_counts(profile: Mapping[str, Any], metric: str) -> dict[str, Any]:
    metrics = _object(profile.get(metric), f"{profile.get('profile')}.{metric}")
    return _object(metrics.get("counts"), f"{profile.get('profile')}.{metric}.counts")


def build_profile_report(source: Mapping[str, Any], *, source_sha256: str) -> dict[str, Any]:
    """Return aggregate profile evidence without protected cases or identifiers."""

    if source.get("schema_version") != 1:
        raise ProfileReportError("unsupported ablation schema_version")
    if len(source_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in source_sha256
    ):
        raise ProfileReportError("source_sha256 must be a lowercase SHA-256 digest")

    corpus = _object(source.get("corpus"), "corpus")
    case_count = _integer(corpus.get("case_count"), "corpus.case_count")
    positive_count = _integer(corpus.get("positive_count"), "corpus.positive_count")
    hard_negative_count = _integer(corpus.get("hard_negative_count"), "corpus.hard_negative_count")
    excluded_review_count = _integer(
        corpus.get("excluded_review_count"), "corpus.excluded_review_count"
    )
    corpus_sha256 = corpus.get("sha256")
    if not isinstance(corpus_sha256, str) or len(corpus_sha256) != 64:
        raise ProfileReportError("corpus.sha256 must be a SHA-256 digest")
    if case_count != positive_count + hard_negative_count:
        raise ProfileReportError("corpus case counts are inconsistent")
    if hard_negative_count == 0:
        raise ProfileReportError("profile gates require hard-negative cases")

    source_profiles = _source_profiles(source)
    profiles = [
        _validated_profile(profile, source_profile_id, source_profiles)
        for profile, source_profile_id in _SOURCE_PROFILE_IDS
    ]
    by_name = {cast(str, profile["profile"]): profile for profile in profiles}
    strict_sentence = _metric_counts(by_name["strict"], "sentence_metrics")
    balanced_sentence = _metric_counts(by_name["balanced"], "sentence_metrics")
    strict_occurrence = _metric_counts(by_name["strict"], "occurrence_metrics")
    balanced_occurrence = _metric_counts(by_name["balanced"], "occurrence_metrics")
    balanced_performance = _object(by_name["balanced"].get("performance"), "performance")
    short_chat = _object(balanced_performance.get("short_chat"), "performance.short_chat")
    maximum_input = _object(balanced_performance.get("maximum_input"), "performance.maximum_input")
    sentence_fp = _integer(balanced_sentence.get("fp"), "balanced.sentence.fp")
    normal_fp_rate = sentence_fp / hard_negative_count
    short_p95 = _number(short_chat.get("p95_ms"), "balanced.short_chat.p95_ms")
    maximum_p95 = _number(maximum_input.get("p95_ms"), "balanced.maximum_input.p95_ms")
    evidence = {
        "sentence_tp_delta_vs_strict": _integer(balanced_sentence.get("tp"), "balanced.sentence.tp")
        - _integer(strict_sentence.get("tp"), "strict.sentence.tp"),
        "sentence_fp_delta_vs_strict": sentence_fp
        - _integer(strict_sentence.get("fp"), "strict.sentence.fp"),
        "occurrence_tp_delta_vs_strict": _integer(
            balanced_occurrence.get("tp"), "balanced.occurrence.tp"
        )
        - _integer(strict_occurrence.get("tp"), "strict.occurrence.tp"),
        "occurrence_fp_delta_vs_strict": _integer(
            balanced_occurrence.get("fp"), "balanced.occurrence.fp"
        )
        - _integer(strict_occurrence.get("fp"), "strict.occurrence.fp"),
    }
    gates = {
        "normal_sentence_fp_rate": normal_fp_rate,
        "normal_sentence_fp_rate_limit": _NORMAL_FP_RATE_LIMIT,
        "short_chat_p95_ms": short_p95,
        "short_chat_p95_ms_limit": _SHORT_CHAT_P95_LIMIT_MS,
        "maximum_input_p95_ms": maximum_p95,
        "maximum_input_p95_ms_limit": _MAXIMUM_INPUT_P95_LIMIT_MS,
        "passed": (
            normal_fp_rate <= _NORMAL_FP_RATE_LIMIT
            and short_p95 <= _SHORT_CHAT_P95_LIMIT_MS
            and maximum_p95 <= _MAXIMUM_INPUT_P95_LIMIT_MS
            and evidence["sentence_tp_delta_vs_strict"] > 0
            and evidence["sentence_fp_delta_vs_strict"] == 0
            and evidence["occurrence_tp_delta_vs_strict"] > 0
            and evidence["occurrence_fp_delta_vs_strict"] == 0
        ),
    }
    measured_at = _string(source.get("measured_at"), "measured_at")
    environment = _object(source.get("environment"), "environment")
    sanitized_environment = {
        key: _string(environment.get(key), f"environment.{key}")
        for key in (
            "koguard_version",
            "python_version",
            "implementation",
            "platform",
            "processor",
        )
    }
    return {
        "schema_version": 1,
        "profile_contract_version": 1,
        "source": {
            "ablation_report_sha256": source_sha256,
            "measured_at": measured_at,
            "corpus": {
                "classification": "independent-tuning-provisional",
                "sha256": corpus_sha256,
                "case_count": case_count,
                "positive_count": positive_count,
                "hard_negative_count": hard_negative_count,
                "excluded_review_count": excluded_review_count,
                "gold_ready": False,
            },
            "environment": sanitized_environment,
        },
        "profiles": profiles,
        "balanced_evidence": evidence,
        "balanced_gates": gates,
        "limitations": [
            f"다중 출처 intake 중 독립 검토로 확정된 {case_count}건만 평가한 tuning 결과다.",
            f"gold_ready가 아니며 {excluded_review_count}건은 review로 자동 평가에서 제외됐다.",
            "hard-negative 30건의 FP 0은 실서비스 전체 FP rate를 일반화하기에 부족하다.",
            "성능은 단일 Windows 로컬 환경 측정이며 지원 OS별 CI 기준선이 아니다.",
        ],
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-ablation", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Write the aggregate-only public report."""

    arguments = _parser().parse_args(argv)
    try:
        if arguments.source_ablation.resolve() == arguments.output.resolve():
            raise ProfileReportError("output must not overwrite the protected input")
        source = _object(
            json.loads(arguments.source_ablation.read_text(encoding="utf-8")),
            "ablation report",
        )
        report = build_profile_report(source, source_sha256=_sha256(arguments.source_ablation))
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {len(report['profiles'])} aggregate profiles to {arguments.output}")
    except (OSError, UnicodeError, json.JSONDecodeError, ProfileReportError) as exc:
        print(f"profile report failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
