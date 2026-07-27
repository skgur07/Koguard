# Benchmark baseline TDD 증거

## Source plan

- [Phase 2 — v0.2 Normalizer + Exact Index + Benchmark](../implementation-plan.md)
- 사용자 여정: 탐지 단계를 추가하는 개발자로서 동일 corpus의 정확도를 보존하면서 지연 시간과
  메모리 변화를 재현 가능한 JSON으로 비교하고 싶다.

## RED

- 테스트: `tests/test_benchmark.py`
- 명령: `uv run pytest --no-cov tests/test_benchmark.py`
- 결과: benchmark 모듈이 없어 import 단계에서 의도대로 실패
- 체크포인트: `70942f5 test: benchmark baseline 동작 계약 추가`

## GREEN

- 구현:
  - JSON corpus 검증과 합성 사전 profile
  - nearest-rank p50/p95, 처리량, cold start, peak memory 측정
  - 기대 매치 수 불일치 시 `BenchmarkError`
  - 환경과 설정을 포함하는 JSON report
- 명령: `uv run pytest --no-cov tests/test_benchmark.py`
- 결과: `5 passed`
- 체크포인트: `47dbd57 feat: 재현 가능한 성능 기준선 도구 구현`

첫 corpus 실행에서는 최대 입력을 10,000자로 잘못 가정해 `InputTooLongError`가 발생했다.
테스트와 corpus를 실제 `EngineConfig.max_input_length`인 4,096자에 맞춘 후 전체 case가
성공했다.

## Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | Phase 2 필수 성능 category와 최대 입력을 corpus가 포함한다 | `test_benchmark_corpus_covers_required_phase_two_scenarios` | unit | PASS |
| 2 | p50/p95가 nearest-rank로 계산된다 | `test_percentile_uses_nearest_rank` | unit | PASS |
| 3 | 지연·처리량·cold start·memory·환경이 기록된다 | `test_run_benchmarks_records_latency_throughput_memory_and_environment` | integration | PASS |
| 4 | 기대 탐지 결과가 달라지면 측정이 실패한다 | `test_run_benchmarks_rejects_accuracy_regression` | integration | PASS |
| 5 | CLI가 stable schema의 JSON을 쓴다 | `test_benchmark_cli_writes_machine_readable_report` | integration | PASS |

## Baseline

- 환경: Windows 10, CPython 3.11.9
- 설정: warmup 10회, 측정 100회
- corpus: 7 cases
- 결과: `benchmarks/results/windows-python311.json`

이 수치는 동일 환경 회귀 비교용이며 장비가 다른 CI의 절대 합격 기준은 아니다. cold start는
한 번 측정한 관찰값이고 peak memory는 Engine 생성 후 한 번의 `check()` allocation 범위다.
