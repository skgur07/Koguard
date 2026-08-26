# PF-005 공통 Exact/Alias FP 재감사 TDD 기록

## 문제

hard-negative buffer 두 batch를 합친 profile 평가에서 strict와 balanced가 같은
`benign-substring` 2건을 문장 FP로 기록했다. balanced만의 Choseong 증분 문제가 아니므로
matcher나 사전을 바꾸기 전에 기존 hard-negative 판정이 문맥 무관 lexical 정책과 일치하는지
독립적으로 다시 확인해야 했다.

## RED와 GREEN

- profile별 `case_results`에서 문장 FP만 선택하는 실패 테스트를 추가했다.
- corpus ID와 canonical SHA-256 불일치, case 누락·중복, profile 누락, 잘못된 outcome을 거부한다.
- `--profile`과 기존 `--matcher`는 동시에 사용할 수 없는 selector로 고정했다.
- 선택 case는 이전 label·span·slice를 제거하고 `review` 상태로만 reviewer에게 전달한다.
- 공개 report와 CLI 출력에는 원문·case ID·canonical term·reviewer ID를 포함하지 않는다.

## 독립 판정과 적용

두 reviewer는 서로의 결과를 보지 않고 2건을 모두 검토했다. 두 사람 모두 positive와 privacy
approved로 판정해 consensus 2건, disagreement 0건이었다. 제3 판정은 필요하지 않았다.
재감사 적용은 immutable ID·원문·출처·라이선스·split을 검증한 뒤 decision field만 교체했다.

| 전이 | 건수 |
| --- | ---: |
| `hard-negative->positive` | 2 |

공개 집계는 다음 두 파일에 저장한다.

- `evaluation/results/pf005-common-exact-fp-reaudit-v1-consensus.report.json`
- `evaluation/results/pf005-common-exact-fp-reaudit-v1-apply.report.json`

## 재측정 결과

평가 가능 표본 수는 1,935건으로 같고 label 구성이 positive 420건, hard-negative 1,515건으로
바뀌었다. review 1,565건은 계속 제외했다.

- strict 문장 TP/FP/FN/TN: 243/0/177/1,515
- balanced 문장 TP/FP/FN/TN: 256/0/164/1,515
- balanced occurrence TP/FP/FN: 328/43/355
- strict 대비 balanced: 문장 TP +13·FP +0, occurrence TP +13·FP +6
- balanced 문장 recall 61.0%, occurrence recall 48.0%

문장 FP 2건은 matcher 결함이 아니라 문맥을 이유로 registered substring을 hard-negative 처리한
annotation 오류였다. 문장 FP는 0건으로 복구됐지만 occurrence FP 증분 6과 hidden 평가 부재는
계속 release blocker다.
