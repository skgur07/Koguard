# PF-003 matcher ablation TDD 기록

## RED

`tests/test_ablation_runner.py`에서 먼저 다음 공개 계약을 고정했다.

- Exact+Alias 기준선, matcher 9개 candidate, Segmented prerequisite control, all-enabled
- sentence 및 exact occurrence TP/FP/FN
- 비교 profile 대비 added/removed, 중복, 고유 증분과 remaining FN
- short/max p50·p95, Engine retained memory와 matcher별 비용 delta
- provisional corpus 분류와 PF-005 재측정 한계
- report 원문 및 canonical term 비수록
- review-only corpus와 잘못된 iteration/warmup 거부

구현 전 테스트는 `ModuleNotFoundError: evaluation.ablation_runner`로 실패했다. 동시에 첫
provisional corpus에서 PF-001 schema가 지원하지 않는 slice 이름도 validator가 차단해 기존
slice 조합으로 바로잡았다.

## GREEN

`evaluation/ablation_runner.py`와 schema version 1을 구현했다. 모든 profile은 matcher
boolean을 명시하고, Segmented는 prerequisite 비용과 기여를 섞지 않도록 별도 control과
비교한다. report는 case ID와 집계만 남기며 원문과 canonical term은 메모리 내 계산 후
폐기한다.

구현과 annotation 대조 과정에서 Alias token-prefix의 span이 전체 토큰이 아니라 실제 alias
표면이어야 함을 발견해 0–3에서 0–2로 수정했다. `시발점`은 annotation 오류가 아니라 기본
whitelist가 비어 있어 Exact부터 발생하는 실제 FP임을 확인해 결과에 그대로 보존했다.

## 측정

CPython 3.11.9에서 100 iterations/10 warmups로
`evaluation/results/provisional-ablation-windows-python311.json`을 생성했다. 각 candidate는
목표 TP 1건을 추가했고 추가 FP는 0건이었다. all-enabled는 TP 11/FP 1/FN 0이며 최대 입력
p95 12.6805ms, retained memory 199,369 bytes였다. 보고서에는 Koguard/Python 버전과 두
workload의 길이·SHA-256도 함께 고정해 이후 실행이 같은 입력을 측정했는지 확인할 수 있다.

이 결과는 구현 유래 20건 regression corpus에서만 유효하다. 독립 서비스 품질, matcher
중복 분포, balanced 포함 여부는 PF-005 corpus 재측정 전까지 확정하지 않는다.
