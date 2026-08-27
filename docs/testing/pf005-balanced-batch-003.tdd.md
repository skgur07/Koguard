# PF-005 balanced batch-003 검증 기록

## 중복 없는 queue

현재 base corpus의 review 1,528건에서 과거 두 balanced batch를 제외했다. 첫 batch는 보호
annotation batch, 두 번째는 보호 queue corpus로 남아 있어 planner가 두 형식을 모두 검증하도록
계약을 확장했다.

- 과거 입력: annotation batch 500건 + queue corpus 500건
- 과거 두 입력의 교집합: 11건
- 과거 고유 검토 사례: 989건
- 현재 review 중 과거 검토 사례: 109건
- 아직 검토하지 않은 eligible 사례: 1,419건
- 새 선택: 500건
- 새 queue와 과거 검토 사례의 교집합: 0건
- 출처 구성: Koguard 65건, KOTE 145건, Curse 145건, Korean Hate Speech 145건

selection은 detector prediction, upstream label과 기존 판정 label을 사용하지 않는다. 원문과
식별자는 보호 경로에만 저장한다.

## 독립 판정

두 reviewer는 서로의 결과를 보지 않고 500건을 모두 판정했다. 완전 합의 136건, 불일치
364건이었고 불일치만 제3 reviewer가 독립 판정했다. 제3 판정은 349건을 해소하고 15건을
`review`로 유지했다. privacy exclude·pending은 없었다.

| 최종 label | 건수 |
| --- | ---: |
| positive | 118 |
| hard-negative | 310 |
| review | 72 |

공개 집계는 다음 두 파일에 저장한다.

- `evaluation/results/pf005-balanced-batch-003-adjudicated.report.json`
- `evaluation/results/pf005-balanced-batch-003-apply.report.json`

## 누적 profile

base corpus에 batch-003 결정을 적용하고 hard-negative buffer 두 batch를 합친 평가 가능 표본은
positive 538건, hard-negative 1,825건으로 총 2,363건이다. review 1,137건은 자동 평가에서
제외했다.

- strict 문장 TP/FP/FN/TN: 334/0/204/1,825
- balanced 문장 TP/FP/FN/TN: 351/0/187/1,825
- balanced occurrence TP/FP/FN: 452/43/380
- strict 대비 balanced: 문장 TP +17·FP +0, occurrence TP +18·FP +6
- balanced 문장 recall 65.2%, occurrence recall 54.3%
- balanced short-chat p95 0.1096ms, 최대 입력 p95 12.0319ms

positive 500건 목표는 충족했지만 hard-negative 2,000건 목표까지 175건이 부족하다. 문장 FP는
0건이고 로컬 성능 예산도 통과했지만 occurrence FP 증분 6과 hidden 평가 부재 때문에 profile
gate와 PF-005는 계속 열린 상태다.
