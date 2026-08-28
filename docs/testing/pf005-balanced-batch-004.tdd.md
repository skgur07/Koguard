# PF-005 balanced batch-004 검증 기록

## 중복 없는 queue와 독립 판정

과거 balanced 세 batch의 고유 검토 사례 1,489건을 제외하고 남은 미검토 919건 중 500건을
결정적인 source round-robin으로 선택했다. 새 queue의 과거 overlap은 0건이고 출처는 KOTE·Curse
각 167건, Korean Hate Speech 166건이다. selection은 detector prediction과 upstream label을
사용하지 않았다.

두 reviewer는 서로의 결과를 보지 않고 500건을 모두 판정했다. 완전 합의 174건, 불일치
326건이었고 불일치만 제3 reviewer가 판정했다. 최종 결과는 positive 100건, hard-negative
300건, review 100건이며 privacy exclude·pending과 계약 오류는 0건이다.

## 공통 FP 재감사와 workflow 회귀

누적 평가에서 strict와 balanced 공통 문장 FP 1건을 찾았다. prior label·span·slice를 제거하고
독립 이중 재감사한 결과 두 reviewer 모두 positive로 판정했으며 span 세부 불일치는 제3 reviewer가
해소했다. 적용 뒤 strict와 balanced 문장 FP는 0건이다.

이 과정에서 profile FP 재감사가 review 사례를 평가 결과에도 요구하는 결함을 재현했다.
`ablation_runner`는 review를 의도적으로 제외하므로 workflow는 source의 non-review case ID와만
case-level evidence를 비교하도록 수정하고 회귀 테스트를 추가했다.

## 최종 누적 profile

- 평가 가능: 2,763건(positive 639, hard-negative 2,124)
- 평가 제외 review: 737건
- strict 문장 TP/FP/FN/TN: 416/0/223/2,124
- balanced 문장 TP/FP/FN/TN: 440/0/199/2,124
- balanced occurrence TP/FP/FN: 579/44/396
- strict 대비 balanced: 문장 TP +24·FP +0, occurrence TP +25·FP +7
- balanced 문장 recall 68.9%, occurrence recall 59.4%
- balanced short-chat p95 0.0212ms, 최대 입력 p95 6.7711ms

PF-005의 positive 500·hard-negative 2,000 수량 기준은 충족했다. 그러나 corpus는 tuning이고
`gold_ready=false`이며, review 737건·hidden 평가 부재·외부 source 재배포 권리·occurrence FP
증분 7이 남아 있어 PF-005와 release gate는 닫지 않는다.

공개 집계는 다음 파일만 사용한다.

- `evaluation/results/pf005-balanced-batch-004-adjudicated.report.json`
- `evaluation/results/pf005-balanced-batch-004-apply.report.json`
- `evaluation/results/pf005-batch-004-common-exact-fp-reaudit-adjudicated.report.json`
- `evaluation/results/pf005-batch-004-common-exact-fp-reaudit-apply.report.json`
