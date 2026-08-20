"""Build public, project-authored PF-005 policy slices as a blinded review intake."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from koguard import KoguardDictionary

CURATED_REPORT_SCHEMA_PATH = Path(__file__).with_name("curated-intake-report.schema.json")
DEFAULT_OUTPUT_PATH = (
    Path(__file__).with_name("corpus") / "tuning" / "curated-policy-slices-v1.json"
)
DEFAULT_REPORT_PATH = Path(__file__).with_name("results") / "curated-policy-slices-v1.report.json"
_CORPUS_ID = "koguard-curated-policy-slices-v1"
_SOURCE_REVISION = "curated-policy-v1"
_POSITIVE_TERMS = (
    "시발",
    "씨발",
    "병신",
    "개새끼",
    "좆",
    "존나",
    "지랄",
    "염병",
    "미친놈",
    "미친년",
    "개년",
    "개놈",
    "느금마",
    "꺼져",
    "닥쳐",
    "등신",
    "머저리",
    "또라이",
    "찐따",
    "틀딱",
)
_HARD_NEGATIVE_SURFACES = (
    "시범",
    "씨앗",
    "병원",
    "개나리",
    "좋다",
    "존중",
    "지리산",
    "염색",
    "미술",
    "미소",
    "개념",
    "개울",
    "느낌",
    "거주",
    "다쳐",
    "등산",
    "머리",
    "또박",
    "진달래",
    "쓰레받기",
    "양치",
    "꼴찌",
    "돌잔치",
    "창문",
    "뒤뜰",
    "닭요리",
    "조선",
    "보조",
    "틀니",
    "따뜻",
)
_POSITIVE_TEMPLATES = (
    ("benign-substring", "{surface}이 포함된 복합 문자열을 차단 정책 예시로 기록합니다."),
    ("quoted-context", "문서에 인용된 표현은 '{surface}'입니다."),
    ("educational-context", "교육 자료에서 {surface}이라는 표현의 사용을 설명합니다."),
    ("username", "검토할 사용자명은 {surface}마스터입니다."),
    ("game-term", "게임 채팅 기록에 {surface}이라고 적혀 있습니다."),
)
_HARD_NEGATIVE_TEMPLATES = (
    ("token-boundary", "{surface} 표기를 경계 비교 대상으로 확인합니다."),
    ("benign-substring", "{surface} 관련 정상 복합어를 기록합니다."),
    ("educational-context", "교육 문서에서 {surface} 항목을 설명합니다."),
    ("username", "검토할 사용자명은 {surface}연구소입니다."),
    ("game-term", "게임 아이템 {surface} 조각을 획득했습니다."),
)


@dataclass(frozen=True, slots=True)
class CuratedIntakeResult:
    """A blinded corpus and non-sensitive design report."""

    corpus: dict[str, Any]
    report: dict[str, Any]


@dataclass(frozen=True, slots=True)
class _DesignedCase:
    text: str
    design_label: str
    design_slice: str


def build_curated_policy_intake(
    *,
    output_path: Path | None = None,
    report_path: Path | None = None,
) -> CuratedIntakeResult:
    """Create deterministic review-only cases without exposing design intent to reviewers."""

    designed = _designed_cases()
    cases = [_blinded_case(item) for item in designed]
    cases.sort(key=lambda case: str(case["id"]))
    design_counts = Counter(item.design_label for item in designed)
    slice_counts = Counter(item.design_slice for item in designed)
    corpus: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": _CORPUS_ID,
        "cases": cases,
    }
    report: dict[str, Any] = {
        "schema_version": 1,
        "corpus_id": _CORPUS_ID,
        "case_count": len(cases),
        "design_counts": {
            "positive_target": design_counts["positive_target"],
            "hard_negative_target": design_counts["hard_negative_target"],
        },
        "design_slice_counts": dict(sorted(slice_counts.items())),
        "source_statistics": [
            {
                "source_id": "koguard-curated-policy",
                "selected_count": len(cases),
                "share": 1.0,
            }
        ],
        "privacy_status": {"synthetic": len(cases), "approved": len(cases)},
        "generated_label_counts": {
            "positive": 0,
            "hard-negative": 0,
            "review": len(cases),
        },
        "gold_ready": False,
        "completion_blockers": [
            "Independent double annotation and disagreement adjudication are still required.",
            "Design intent is not a substitute for Koguard-policy gold annotation.",
        ],
    }
    result = CuratedIntakeResult(corpus=corpus, report=report)
    if output_path is not None:
        _write_json(output_path, corpus)
    if report_path is not None:
        _write_json(report_path, report)
    return result


def _designed_cases() -> tuple[_DesignedCase, ...]:
    positive = tuple(
        _DesignedCase(
            text=template.format(surface=term),
            design_label="positive_target",
            design_slice=slice_name,
        )
        for term in _POSITIVE_TERMS
        for slice_name, template in _POSITIVE_TEMPLATES
    )
    hard_negative = tuple(
        _DesignedCase(
            text=template.format(surface=surface),
            design_label="hard_negative_target",
            design_slice=slice_name,
        )
        for surface in _HARD_NEGATIVE_SURFACES
        for slice_name, template in _HARD_NEGATIVE_TEMPLATES
    )
    if len(positive) != 100 or len(hard_negative) != 150:
        raise RuntimeError("curated policy design count changed unexpectedly")
    dictionary = KoguardDictionary.default()
    forbidden_surfaces = dictionary.blacklist | frozenset(rule.alias for rule in dictionary.aliases)
    if any(
        term not in template.format(surface=term)
        for term in _POSITIVE_TERMS
        for _, template in _POSITIVE_TEMPLATES
    ):
        raise RuntimeError("curated positive design lost its target surface")
    if any(forbidden in item.text for item in hard_negative for forbidden in forbidden_surfaces):
        raise RuntimeError("curated hard-negative design contains a packaged surface")
    designed = positive + hard_negative
    if len({item.text for item in designed}) != len(designed):
        raise RuntimeError("curated policy design contains duplicate text")
    return designed


def _blinded_case(item: _DesignedCase) -> dict[str, Any]:
    identity = hashlib.sha256(
        f"{_CORPUS_ID}\0{item.design_label}\0{item.design_slice}\0{item.text}".encode()
    ).hexdigest()
    return {
        "id": f"koguard-curated-review-{identity[:20]}",
        "text": item.text,
        "label": "review",
        "expected_matches": [],
        "slices": ["unadjudicated-intake"],
        "source": {
            "kind": "curated",
            "name": "Koguard curated policy slices",
            "reference": "https://github.com/skgur07/Koguard",
            "revision": _SOURCE_REVISION,
            "redistribution_allowed": True,
        },
        "license": "MIT",
        "split": "tuning",
        "notes": "Unadjudicated project-authored policy slice.",
    }


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Generate the curated review intake and print aggregate counts only."""

    arguments = _parser().parse_args(argv)
    result = build_curated_policy_intake(
        output_path=arguments.output,
        report_path=arguments.report,
    )
    print(f"cases={result.report['case_count']}; gold_ready=false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
