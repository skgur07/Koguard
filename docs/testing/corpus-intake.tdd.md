# PF-005 corpus intake TDD 기록

## RED

source spec·report closed schema, 고정 artifact hash, deterministic 층화, review-only 변환,
validator 호환, 원문 비노출, quota 부족과 hash mismatch 실패를 먼저 테스트했다. 구현 전에는
`evaluation.corpus_intake`가 없어 수집 단계에서 실패했다.

stable-ID split manifest v2 생성도 기존 assignment 보존과 version 증가 테스트를 먼저 추가했고
`evaluation.split_manifest_builder` 부재로 RED를 확인했다.

## GREEN

`corpus_intake.py`는 네트워크 없이 고정 artifact를 검사하고 source label별 SHA-256 rank로
2,500건을 선택한다. upstream label은 gold로 복사하지 않으며 모든 case는 tuning `review`로
생성한다. report에는 원문 없이 source/selected count와 `gold_ready=false` blockers만 남긴다.

`split_manifest_builder.py`는 기존 20개 assignment의 누락·이동을 차단하면서 2,500 stable ID를
manifest v2에 추가한다. 결과는 regression 20, tuning review 2,500, 누출 0건이다.

## 한계

PF-005의 수집·재현 기반은 마련됐지만 사람의 Koguard-policy 판정, exact span, 독립 hidden
evaluation은 아직 없다. 이 상태를 완료 corpus로 오인하지 않도록 checked report와 문서에
blocker를 고정하고 GitHub #7은 열린 상태로 유지한다.
