# PF-005 hard-negative buffer batch-002 검증 기록

## 목적과 중복 방지

첫 500건과 겹치지 않는 나머지 review buffer 500건을 독립 판정했다. queue planner에
`--exclude-corpus`를 추가해 이전 queue의 stable ID와 원문·출처·라이선스·split 식별자가
일치하는 case를 선택 전에 제외하도록 계약 테스트를 먼저 고정했다.

- 전체 buffer: 1,000건
- 이전 queue 제외: 500건
- 선택 가능·선택 완료: 500건
- 이전 batch와 교집합: 0건
- 출처 구성: KOTE 166건, Curse 167건, Korean Hate Speech 167건

원문, case ID, canonical term, reviewer 식별자는 보호 경로에만 저장하고 공개 보고서는 집계만
포함한다.

## 독립 검토와 제3 판정

두 reviewer는 서로의 결과와 detector prediction을 보지 않고 500건을 모두 판정했다. 완전
합의는 16건, 불일치는 484건이었다. 불일치만 독립 제3 판정에 전달했고 473건을 해소했으며
11건은 `review`로 유지했다. 개인정보 제외·대기는 없었다.

| 최종 label | 건수 |
| --- | ---: |
| positive | 29 |
| hard-negative | 451 |
| review | 20 |

공개 집계는
`evaluation/results/pf005-hard-negative-batch-002-adjudicated.report.json`에 저장한다.

## 누적 profile 재측정

기존 확정 corpus와 hard-negative buffer 두 batch를 합친 평가 가능 표본은 positive 418건,
hard-negative 1,517건으로 총 1,935건이다. review 1,565건은 자동 평가에서 제외했다.

- strict 문장 TP/FP/FN/TN: 241/2/177/1,515
- balanced 문장 TP/FP/FN/TN: 254/2/164/1,515
- balanced occurrence TP/FP/FN: 326/45/355
- strict 대비 balanced 증분: 문장 TP +13·FP +0, occurrence TP +13·FP +6
- balanced 문장 recall 60.8%, occurrence recall 47.9%
- balanced 문장 FP rate 2/1,517(0.132%), 임시 0.5% 예산 이내

문장 FP 2건은 strict와 balanced가 공통으로 발생시킨다. balanced가 새 문장 FP를 추가하지는
않지만 occurrence FP 증분이 6건이므로 전체 FP 증분 0 gate는 계속 실패한다. 이 결과는
`gold_ready=false`인 tuning 평가이며 hidden 평가나 실서비스 품질 수치가 아니다.

## 남은 조건

- positive 500건 목표까지 82건, hard-negative 2,000건 목표까지 483건을 추가 확정한다.
- 기존 intake review 1,528건과 buffer review 37건을 독립 판정한다.
- 문장 FP 2건의 원인을 별도 hard-negative 분석으로 분류하고 회귀 테스트 후보를 만든다.

## 후속 재감사

위 문장 FP 2건은 `docs/testing/pf005-common-exact-fp-reaudit.tdd.md` 절차로 다시 판정했다. 두
reviewer가 모두 문맥 무관 core positive로 합의해 `hard-negative->positive` 2건을 적용했고,
수정 후 strict와 balanced의 문장 FP는 0건이다. 이 절의 최초 batch 수치는 재감사 전 역사적
측정으로 보존한다.
- 별도 custodian이 누출되지 않은 hidden corpus를 구축해 동일 profile 계약으로 재평가한다.
