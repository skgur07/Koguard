# PF-007 false-negative candidate evaluation TDD 기록

## RED

보호 corpus와 provenance candidate를 받아 원문 없이 증분 TP·FP·FN을 내는 모듈이 없어 import
단계에서 실패함을 확인했다. 닫힌 report schema, 현재 기본 사전 기준선, 후보 개별·결합 결과,
positive/hard-negative support와 raw term 비노출을 먼저 테스트로 고정했다.

## GREEN

`evaluation.fn_candidate_evaluation`은 승인 source의 core exact literal `candidate`만 평가한다.
문장 단위 TP/FP/FN/TN과 `(start, end, canonical)` occurrence TP/FP/FN을 함께 비교하며 report에는
stable candidate ID와 aggregate만 남긴다. 첫 7개 후보 평가에서 결합 sentence TP +10/FP +0,
occurrence TP +20/FP -1을 확인했고 개별 5개가 tuning gate를 통과했다.

## 남은 작업

두 실패 후보는 효과 없음 또는 occurrence 정합성 비용 때문에 그대로 승격하지 않는다. 통과
후보도 hidden evaluation이 없으므로 `candidate` 상태를 유지한다. PF-005의 다음 독립 batch로
support와 FP 예산을 늘리고 hidden gate를 통과한 뒤에만 packaged data 변경을 검토한다.
