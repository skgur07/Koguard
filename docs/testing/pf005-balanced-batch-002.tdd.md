# PF-005 정책 재감사·balanced batch-002 검증 기록

## 목적

2026-08-20 tuning에서 Choseong 증분 FP로 분류된 3건을 현재 문맥 무관 lexical 정책으로
재감사하고, 남은 review 중 네 출처에서 각각 125건을 선택한 다음 500건을 추가 확정한다.
기존 label, detector prediction, packaged dictionary와 reviewer 간 판정은 모두 차단한다.

## 독립성·복구 경계

- Primary와 Secondary는 policy 3건과 batch 500건을 서로 독립적으로 판정했다.
- 한 Primary 작업 파일이 직렬화 중 손상됐을 때 다른 reviewer 결과나 기존 label을 사용하지 않고
  중립 review queue에서 같은 annotation set만 다시 export했다.
- 복구 뒤 100건 단위 `apply_patch`와 JSON·case 순서·원문 불변 검증을 통과했다.
- 제3 판정자는 앞선 두 판정값 없이 불일치한 1-based 순번과 중립 원문만 받았다.
- 보호 원문, case ID, canonical term, reviewer ID는 Git과 공개 report에 포함하지 않았다.

## 정책 재감사 결과

| 항목 | 값 |
| --- | ---: |
| 재감사 대상 | 3 |
| 완전 consensus | 0 |
| 세부 판정 불일치 | 3 |
| 제3 판정 확정 | 3 |
| 최종 positive | 3 |
| `positive->positive` | 2 |
| `hard-negative->positive` | 1 |

두 역할 모두 label은 positive로 보았지만 span·canonical·slice 결정이 달라 정식 decision key는
3건 모두 불일치였다. 제3 판정 뒤 `reaudit_workflow apply`가 원문·source·license·split 불변과
prepared/adjudication hash를 확인하고 decision 필드만 보호 corpus에 반영했다.

## balanced batch-002 결과

| 항목 | 값 |
| --- | ---: |
| batch | 500 |
| 출처별 선택 | 125/125/125/125 |
| 완전 consensus | 207 |
| 불일치 | 293 |
| 제3 판정 확정 | 281 |
| 제3 판정 review 유지 | 12 |
| 최종 positive | 112 |
| 최종 hard-negative | 324 |
| 최종 review | 64 |
| privacy 제외·대기 | 0 |

정책 재감사와 batch-002를 반영한 2,500건 corpus는 positive 377, hard-negative 595,
review 1,528이며 `gold_ready=false`다. 공개 가능한 집계만 다음 파일에 저장했다.

- `evaluation/results/pf005-policy-reaudit-v1-adjudicated.report.json`
- `evaluation/results/pf005-policy-reaudit-v1-apply.report.json`
- `evaluation/results/pf005-balanced-batch-002-adjudicated.report.json`

## profile·PF-007 재측정

| profile | 문장 TP/FP/FN/TN | 문장 recall | occurrence TP/FP/FN | occurrence recall |
| --- | --- | ---: | --- | ---: |
| strict | 231/0/146/595 | 61.3% | 302/37/332 | 47.6% |
| balanced | 241/0/136/595 | 63.9% | 314/41/320 | 49.5% |
| aggressive | 250/10/127/585 | 66.3% | 318/63/316 | 50.2% |

balanced는 strict 대비 문장 TP +10·FP +0, occurrence TP +12·FP +4다. hard-negative 문장
FP rate와 short/max p95 예산은 통과했지만 occurrence FP 증분 0 조건 때문에 profile gate는
실패한다. 성능은 단일 Windows 로컬 측정이며 hidden 또는 지원 OS 전체 기준선이 아니다.

보류 candidate `core.literal.pf007.007`은 972건에서 문장 변화 없이 occurrence TP +2·FP -2로
tuning gate를 다시 통과했다. hidden 평가 전에는 packaged로 승격하지 않는다.

## 검증 명령

```powershell
uv run python -m evaluation.annotation_workflow merge <protected paths>
uv run python -m evaluation.annotation_workflow adjudicate <protected paths>
uv run python -m evaluation.reaudit_workflow apply <protected paths>
uv run python -m evaluation.corpus_validator <protected corpus>
uv run python -m evaluation.ablation_runner --corpus <protected corpus> --output <protected report> --iterations 100 --warmups 10
uv run python -m evaluation.profile_report --source-ablation <protected report>
uv run python -m evaluation.fn_candidate_evaluation <protected corpus> evaluation/dictionary-provenance.v1.json --output <aggregate report>
uv run pytest
```

## 남은 제한

- review 1,528건이 남아 전체 corpus는 gold가 아니다.
- positive 500건·hard-negative 2,000건 목표와 unresolved 여유를 위해 최소 1,000건의
  hard-negative 중심 review buffer가 더 필요하다.
- KOTE·BEEP privacy와 CC-BY-SA attribution 경계, 독립 hidden evaluation은 별도 완료해야 한다.
