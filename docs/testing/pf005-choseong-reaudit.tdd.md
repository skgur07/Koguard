# PF-005 초성 재감사와 다음 queue TDD 기록

## 문제

추가 500건 tuning에서 Choseong은 strict 대비 문장 TP 6건과 occurrence TP 7건을 추가했지만,
동일한 2자 초성 표면 하나에서 문장 FP 1건과 occurrence FP 3건도 추가했다. 이 표면은
`domain-term` hard-negative 1건과 positive 문장의 누락 occurrence 2건에 걸쳐 있어, matcher
결함과 문맥 무관 annotation 정책 충돌을 먼저 분리해야 한다.

기존 balanced intake는 2,500건이고 완료 목표도 positive 500건과 hard-negative 2,000건의 합인
2,500건이다. 현재 review 1,964건 중 하나라도 unresolved로 남으면 기존 intake만으로 완료 조건을
만족할 여유가 없다.

## RED

- matcher report와 다른 corpus를 결합한 재감사를 거부하는 테스트
- 이전 label·span·slice가 reviewer 입력에 남는 재감사 준비를 거부하는 테스트
- 재감사 결과 적용 시 원문·출처·라이선스·split 변경을 거부하는 테스트
- 다음 500건 queue가 finalized case를 포함하거나 한 출처에 치우치는 경우를 검출하는 테스트
- aggregate report가 원문이나 case ID를 포함하지 않는지 확인하는 테스트

## GREEN

- `evaluation.reaudit_workflow`가 보호 ablation의 matcher FP case만 선택하고 corpus ID와 canonical
  SHA-256을 검증하도록 구현했다.
- 선택 사례는 `review`, 빈 expected match, `unadjudicated-intake`로 초기화해 기존 결정을
  reviewer에게 노출하지 않는다.
- adjudicated 결과 적용 시 immutable case field를 검증하고 decision field만 교체한다.
- `evaluation.review_queue_planner`가 review case만 source round-robin SHA-256 방식으로 최대
  500건 선택한다.

## 보호 실행 결과

- Choseong FP 재감사 대상: 3건
- primary·secondary reviewer 입력: 각 3건
- 다음 balanced batch queue: 500건
- 출처별 선택: Koguard curated, KOTE, Curse-detection-data, Korean Hate Speech 각 125건
- 원문·case ID·canonical term은 공개 산출물과 CLI 출력에서 제외

후속 독립 판정·제3 판정·보호 corpus 적용과 재측정은
[`pf005-balanced-batch-002.tdd.md`](pf005-balanced-batch-002.tdd.md)에 기록했다. 최종 재감사
3건은 모두 positive였고, 실제 label 전이는 `hard-negative->positive` 1건과
`positive->positive` 2건이었다.
