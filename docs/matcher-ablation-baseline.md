# PF-003 matcher ablation provisional 기준선

측정일: 2026-08-13 09:56 KST

환경: Koguard 0.1.0, CPython 3.11.9, Windows 10.0.26200, Intel64 Family 6 Model 170
반복: workload별 100회, warmup 10회

## 결론

문맥 무관 lexical core 정책에 따라 정상 복합어와 명시적 공백·초성·두벌식 우회 5건을
positive로 재분류했다. 현재 all-enabled는 이 20건의 구현 유래 regression corpus에서
positive 16건 중 12건을 찾고 4건을 놓쳤으며, 정책 표현이 없는 hard-negative 4건에서는 FP가
없었다. PF-005의 독립 positive 500건·negative 2,000건 corpus에서 동일 runner를 다시 실행하기
전까지 현재 결과는 도구 검증과 비용의 provisional 기준선으로만 사용한다.

모든 고급 matcher가 각자 목표로 만든 positive 1건을 추가했고 새 FP는 만들지 않았다. 이는
matcher가 유용하다는 독립 증거가 아니라 해당 구현 경로를 fixture가 정상적으로 자극한다는
증거다. matcher 간 동일 occurrence 중복은 0건이었지만, corpus가 작고 각 matcher별 사례가
분리되어 있으므로 실제 중복이 없다는 뜻이 아니다.

## 측정 계약

- 기준선: Exact + Alias
- candidate: 기준선에 matcher 하나만 추가
- Segmented: Keyboard + Jamo + Choseong prerequisite control과 비교
- current: 모든 matcher를 명시적으로 활성화한 현재 기본 동작
- 정확도: sentence 및 `(case_id, start, end, canonical)` occurrence TP/FP/FN
- 기여: 비교 profile 대비 added/removed TP·FP, 기준선 중복, matcher 간 중복, 고유 증분
- 비용: short-chat와 4,096자 입력 p50/p95, fresh Engine retained Python allocation
- 개인정보 경계: report에는 corpus 원문이나 canonical term을 기록하지 않음

## 전체 profile 비교

| profile | sentence TP/FP/FN/TN | occurrence TP/FP/FN | short p50/p95 ms | max p50/p95 ms | retained bytes |
| --- | --- | --- | ---: | ---: | ---: |
| Exact+Alias | 3/0/13/4 | 3/0/13 | 0.0315/0.0359 | 6.4133/7.0212 | 70,514 |
| all-enabled | 12/0/4/4 | 12/0/4 | 0.1009/0.1144 | 11.3184/12.2350 | 199,302 |

all-enabled는 이 환경에서 임시 성능 예산인 short-chat p95 1ms와 최대 입력 p95 15ms 안에
들었다. provisional hard-negative FP는 0/4지만 표본이 너무 작아 비율을 일반화할 수 없다.
반면 strict 정책상 positive 4건을 놓쳤으므로, 독립 판정 후 동일한 미탐 유형이 확인되면
사전·구분자·공백·두벌식 경계를 우선 보강해야 한다.

## matcher별 provisional 기여와 비용

| matcher | added TP/FP | unique TP | overlap | remaining FN | short p95 Δ ms | max p95 Δ ms | retained Δ bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Repeated | 1/0 | 1 | 0 | 12 | +0.0078 | -0.2600 | +67 |
| Separator | 1/0 | 1 | 0 | 12 | +0.0121 | -0.1551 | 0 |
| Whitespace | 1/0 | 1 | 0 | 12 | +0.0217 | -0.2388 | +25,772 |
| Mixed | 1/0 | 1 | 0 | 12 | +0.0162 | -0.0539 | +38,583 |
| Keyboard | 1/0 | 1 | 0 | 12 | +0.0058 | +1.0168 | 0 |
| Jamo | 1/0 | 1 | 0 | 12 | +0.0267 | -0.1724 | 0 |
| Choseong | 1/0 | 1 | 0 | 12 | +0.0221 | +2.2714 | +37,861 |
| Segmented | 1/0 | 1 | 0 | 9 | -0.0136 | -0.0779 | -67 |
| Fuzzy | 1/0 | 1 | 0 | 12 | +0.1124 | +2.4512 | +20,293 |

Segmented의 delta는 Exact+Alias가 아니라 prerequisite control과 비교한 값이다. 음수 latency
delta와 67 bytes 수준의 retained 차이는 기능 비활성화가 빨라졌거나 메모리를 더 쓴다는
결론이 아니라 단일 프로세스 microbenchmark 노이즈로 해석한다. 지원 OS matrix와 독립
corpus를 확보하기 전에는 작은 차이로 matcher를 선택하지 않는다.

## 재현

```powershell
uv run python -m evaluation.ablation_runner `
  --corpus evaluation\corpus\provisional-ablation.json `
  --output evaluation\results\provisional-ablation-windows-python311.json `
  --iterations 100 `
  --warmups 10
```

- corpus semantic SHA-256: `4ad85de87665defd4fdfbe9eca89884a9f1f8fa228fd005c4afc45c862bc2ce7`
- profile configuration SHA-256:
  `3fcd74ed874c2cafe514b1497c65e07b06421eb2807c09583184b76ad7b7fb93`
- short-chat workload SHA-256:
  `e40b61e7150bac2daf644dcc8f287f53864d62f9a82f100edde6fcf326f9dde4`
- maximum-input workload SHA-256:
  `8f13cf6f530d53ddba47fc5515034cce5841077fcf0473ea1ae761b923eeceba`
- machine-readable report:
  `evaluation/results/provisional-ablation-windows-python311.json`

## 후속 진행 상태

1. PF-004에서 tuning과 hidden evaluation을 물리적으로 분리했다.
2. PF-005 첫 독립 이중 판정 batch 100건 중 92건을 확정해 이 runner로 다시 평가했다.
3. PF-008/009에서 Exact+Alias+Choseong을 balanced로 확정하고 공개 profile API를 구현했다.
4. 공개 집계와 한계는
   [`pf009-profile-evaluation.report.json`](../evaluation/results/pf009-profile-evaluation.report.json)에
   기록한다.
5. 2026-08-19에는 2,500건 다중 출처 intake에 기존 확정 92건을 보존한 상태로 최종 후보
   사전을 재측정했다. balanced 문장 TP/FP/FN/TN은 45/0/17/30이고 occurrence TP/FP/FN은
   59/11/51이다.
6. 2026-08-20 추가 500건을 독립 이중 판정하고 불일치 387건을 제3 판정해 총 536건을 확정했다.
   balanced 문장 TP/FP/FN/TN은 141/1/123/271이고 occurrence TP/FP/FN은 197/32/283이다.
7. 2026-08-25 정책 재감사 3건과 다음 500건을 독립 판정하고 불일치 3건·293건을 제3 판정해
   총 972건을 확정했다. balanced 문장 TP/FP/FN/TN은 241/0/136/595이고 occurrence
   TP/FP/FN은 314/41/320이다. strict 대비 문장 FP 증분은 0으로 개선됐지만 occurrence FP
   증분 4건 때문에 전체 gate는 실패한다.
8. 2026-08-26 hard-negative buffer의 첫 500건을 독립 판정해 12 positive, 471 hard-negative를
   확정했다. 총 1,455건에서 balanced 문장 TP/FP/FN/TN은 243/0/146/1,066이고 occurrence
   TP/FP/FN은 316/41/332다. strict 대비 문장 TP +10·FP +0, occurrence TP +12·FP +4다.
9. 같은 날 이전 queue와 겹치지 않는 나머지 500건을 독립 판정해 29 positive,
   451 hard-negative를 확정했다. 총 1,935건에서 balanced 문장 TP/FP/FN/TN은
   254/2/164/1,515이고 occurrence TP/FP/FN은 326/45/355다. strict 대비 문장 TP +13·FP +0,
   occurrence TP +13·FP +6이다.
10. 공통 문장 FP 2건을 블라인드 재감사해 두 reviewer가 모두 policy positive로 합의했다. 수정한
   총 1,935건에서 balanced 문장 TP/FP/FN/TN은 256/0/164/1,515이고 occurrence TP/FP/FN은
   328/43/355다.
11. 2026-08-27 과거 고유 검토 사례 989건과 겹치지 않는 새 500건을 판정해 positive 118,
   hard-negative 310건을 확정했다. 총 2,363건에서 balanced 문장 TP/FP/FN/TN은
   351/0/187/1,825이고 occurrence TP/FP/FN은 452/43/380이다. strict 대비 문장 TP +17·FP +0,
   occurrence TP +18·FP +6이다.
12. 2026-08-28 과거 세 batch와 겹치지 않는 500건을 판정해 positive 100, hard-negative 300건을
   확정했다. 공통 문장 FP 1건을 policy positive로 재감사한 뒤 총 2,763건에서 balanced 문장
   TP/FP/FN/TN은 440/0/199/2,124이고 occurrence TP/FP/FN은 579/44/396이다. strict 대비
   문장 TP +24·FP +0, occurrence TP +25·FP +7이다.
13. PF-005의 positive 500·hard-negative 2,000 수량 기준은 충족했다. 다음 결정은 hidden 평가,
   출처 재배포 권리, slice 품질과 occurrence FP gate이며 그 전에는 현재 profile 수치를 실서비스
   전체로 일반화하지 않는다.
