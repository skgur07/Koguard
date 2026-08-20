# PF-005 balanced batch 001 검증 기록

## 목적

다중 출처 balanced tuning composition의 다음 500건을 이전 detector 결과와 upstream label 없이
독립 판정하고, 불일치를 제3 판정으로 처리한 뒤 공개 가능한 집계만 저장한다.

## 독립성 경계

- Primary와 Secondary는 서로의 JSON, 기존 결과, detector, packaged dictionary를 열람하지 않았다.
- 제3 검토자는 이전 두 판정값 없이 불일치한 1-based 순번만 전달받았다.
- 세 작업 파일과 최종 corpus 원문은 `evaluation/annotation-work/`에 두어 Git과 배포물에서
  제외했다.
- 공개 report에는 원문, case ID, canonical term, reviewer ID를 포함하지 않았다.

## RED와 계약 보정

첫 공식 merge는 approved `review` 사례가 실제 slice를 가진 상태를 거부했다.

```text
annotation workflow failed: cases[6] approved review must remain unadjudicated
```

각 검토자가 자기 파일의 `review` 사례만 `slices=["unadjudicated-intake"]`로 보정했고 label,
privacy, 원문, notes는 바꾸지 않았다. 이후 공식 merge가 원본 corpus SHA-256, case 원문,
reviewer와 annotation set 독립성 및 모든 span 계약을 검증했다.

## 판정 결과

| 항목 | 값 |
| --- | ---: |
| batch | 500 |
| label 일치 | 464 |
| 완전 consensus | 113 |
| 불일치 | 387 |
| 제3 판정 확정 | 334 |
| 제3 판정 review 유지 | 53 |
| 최종 positive | 202 |
| 최종 hard-negative | 242 |
| 최종 review | 56 |
| privacy 제외·대기 | 0 |

기존 첫 batch와 합친 corpus 집계는 positive 264, hard-negative 272, review 1,964이며
`gold_ready=false`다. 공개 집계는
`evaluation/results/pf005-balanced-batch-001-adjudicated.report.json`에 저장한다.

## Profile 재측정

| profile | 문장 TP/FP/FN/TN | 문장 recall | occurrence TP/FP/FN | occurrence recall |
| --- | --- | ---: | --- | ---: |
| strict | 135/0/129/272 | 51.1% | 190/29/290 | 39.6% |
| balanced | 141/1/123/271 | 53.4% | 197/32/283 | 41.0% |
| aggressive | 149/2/115/270 | 56.4% | 200/43/280 | 41.7% |

balanced는 성능과 전체 hard-negative FP rate 예산은 통과했지만 strict 대비 FP 증분 0 조건을
통과하지 못했다. 이 결과는 tuning이며 hidden 또는 실서비스 정확도가 아니다.

## 검증 명령

```powershell
uv run python -m evaluation.annotation_workflow adjudicate <protected paths>
uv run python -m evaluation.corpus_validator <protected adjudicated corpus>
uv run python -m evaluation.ablation_runner --corpus <protected corpus> --output <protected report>
uv run python -m evaluation.profile_report --source-ablation <protected report>
uv run pytest
```
