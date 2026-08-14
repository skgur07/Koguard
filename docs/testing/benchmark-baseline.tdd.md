# Benchmark baseline TDD 증거

> 후속 변경: 이 문서는 최초 profile과 기준선의 TDD 근거를 보존한다. 벤치마크의 `default`는
> 직접 `EngineConfig()`를 만든 all-enabled 호환성 설정이며, 공개 API 기본값은 PF-009부터
> `balanced`다. 현재 계약은 [`profile-api-contract.tdd.md`](profile-api-contract.tdd.md)와
> [`../../benchmarks/README.md`](../../benchmarks/README.md)를 따른다.

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
- corpus: 15 cases
- 결과: `benchmarks/results/windows-python311.json`

이 수치는 동일 환경 회귀 비교용이며 장비가 다른 CI의 절대 합격 기준은 아니다. cold start는
한 번 측정한 관찰값이고 peak memory는 Engine 생성 후 한 번의 `check()` allocation 범위다.

## 공백 매칭 profile 확장

공백 매칭은 opt-in 기능이므로 기본 엔진만 측정하는 기존 corpus로는 기능의 정확도와 성능
회귀를 비교할 수 없었다. case별 `engine_profile`을 추가하고 report schema를 2로 올려 결과마다
실제 측정 설정을 기록했다.

### RED

- 테스트: `tests/test_benchmark.py`
- 명령: `.venv\Scripts\python.exe -m pytest tests/test_benchmark.py -q --no-cov`
- 결과: profile 계약과 schema 2, 새 corpus 및 기준선이 없어 `6 failed, 2 passed`
- 체크포인트: `a9a0156 test: 공백 매칭 benchmark 프로필 계약 추가`

### GREEN

- `default`와 `whitespace-gap` 엔진 profile을 지원하고 알 수 없는 profile은 거부한다.
- `시 발` 긍정 사례와 `시 발표` 경계 오탐 방지 사례를 고정했다.
- 256개 공통 접두사와 4,096자 공백 입력을 결합해 최악 후보 경로를 측정한다.
- corpus와 Windows 기준선의 case 이름 및 profile이 정확히 일치하는지 테스트한다.
- 기준선 명령:
  `.venv\Scripts\python.exe -m benchmarks.engine_benchmark --corpus benchmarks\corpus.json
  --iterations 100 --warmups 10 --output benchmarks\results\windows-python311.json`
- 결과: schema 2의 11개 case 기록

### 추가 Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 6 | 공백 profile이 opt-in 엔진 설정을 적용한다 | `test_run_benchmarks_applies_whitespace_gap_engine_profile` | integration | PASS |
| 7 | 알 수 없는 엔진 profile은 측정 전에 실패한다 | `test_run_benchmarks_rejects_unknown_engine_profile` | unit | PASS |
| 8 | 기준선과 corpus의 순서 및 전체 workload가 일치한다 | `test_windows_baseline_matches_ordered_complete_corpus_cases` | integration | PASS |

## 리뷰 수정 RED/GREEN

리뷰에서 기준선 검증이 case 이름과 엔진 profile의 집합만 비교해 입력이나 사전 구성이 바뀐
오래된 기준선과 중복 결과를 허용할 수 있음을 확인했다.

### RED

- 전체 workload fingerprint와 순서 보존 비교 계약을 테스트에 추가했다.
- 명령: `.venv\Scripts\python.exe -m pytest tests\test_benchmark.py -q --no-cov`
- 결과: `benchmark_case_fingerprint`가 없어 collection 단계에서 의도대로 실패
- 체크포인트: `09e22c9 test: benchmark 기준선 무결성 결함 재현`

### GREEN

- `BenchmarkCase`의 모든 필드를 canonical JSON으로 직렬화하고 SHA-256 fingerprint를 만든다.
- 각 결과에 `dictionary_profile`과 `case_fingerprint`를 기록한다.
- 기준선과 corpus의 fingerprint를 list로 비교해 입력·사전·기대값 변경, 순서 변경, 중복 및
  누락을 모두 탐지한다.
- 구현 후 이전 기준선에 fingerprint가 없어 `8 passed, 1 failed`인 것을 확인하고, 100회·
  warmup 10회 설정으로 11개 case 기준선을 다시 생성했다.

### 추가 Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 9 | fingerprint가 모든 workload 필드 변경을 구분한다 | `test_benchmark_case_fingerprint_covers_complete_workload_definition` | unit | PASS |
| 10 | report가 사전 profile과 fingerprint를 기록한다 | `test_run_benchmarks_records_latency_throughput_memory_and_environment` | integration | PASS |

## Engine retained memory 측정 보강

리뷰에서 기존 `peak_memory_bytes`가 이미 생성된 Engine의 `check()` allocation만 측정해,
공백 매칭을 활성화할 때 추가되는 matcher index의 보유 메모리를 기준선에 남기지 못함을
확인했다.

### RED

- 테스트: `tests/test_benchmark.py`
- 명령: `.venv\Scripts\python.exe -m pytest tests\test_benchmark.py -q --no-cov`
- 결과: `BenchmarkResult.engine_retained_memory_bytes`와 schema 3이 구현되지 않았고, 1,000개
  사전의 공백 profile corpus case가 없어 의도대로 실패

### GREEN

- tracing 시작 후 새 Engine과 사전을 생성하고 생성 직후의 current Python allocation을
  `engine_retained_memory_bytes`로 기록한다.
- 기존 `peak_memory_bytes`는 생성된 Engine에서 한 번 실행한 `check()`의 peak allocation이라는
  의미를 유지한다.
- 1,000개 표준 사전과 `whitespace-gap` profile에서 `시 * 발`을 검사하는 corpus case를 추가해
  혼합 matcher index의 retained memory가 기준선에 포함되도록 했다.
- 두 지표 모두 `tracemalloc`이 관찰하는 Python allocation이며 프로세스 RSS나 native
  allocation은 포함하지 않는다.
- targeted GREEN 명령:
  `.venv\Scripts\python.exe -m pytest tests\test_benchmark.py -q --no-cov -k "not windows_baseline"`
- targeted GREEN 결과: `10 passed, 1 deselected` (Windows 기준선 JSON 재생성 전)
- 기준선 재측정: CPython 3.11.9, warmup 10회·측정 100회, schema 3의 15개 case
- 기준선 재측정 후 전체 benchmark 테스트: `11 passed`

### 추가 Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 11 | report가 새 Engine 생성 직후의 retained Python allocation을 기록한다 | `test_run_benchmarks_records_latency_throughput_memory_and_environment` | integration | PASS |
| 12 | opt-in matcher index를 포함한 profile이 기본 profile보다 많은 retained memory를 기록한다 | `test_retained_memory_includes_opt_in_matcher_indexes` | integration | PASS |
| 13 | corpus가 1,000개 사전의 공백 profile workload를 포함한다 | `test_benchmark_corpus_covers_required_phase_two_scenarios` | unit | PASS |
| 14 | tracing을 시작한 뒤 fresh Engine을 만들어 retained allocation을 포착한다 | `test_retained_memory_starts_tracing_before_fresh_engine_creation` | integration | PASS |

## Retained memory allocator 상태 격리

후속 리뷰에서 retained memory 측정이 앞서 실행한 입력 크기에 따라 달라지는 것을 확인했다.
측정 대상 Engine이 같아도 CPython allocator와 free list에 남은 이전 workload의 상태가
`tracemalloc` 현재값에 섞여 기준선 비교를 왜곡했다.

### RED

- 동일한 기본 Engine을 짧은 입력과 최대 입력 뒤에 각각 생성하는 회귀 테스트를 추가했다.
- 결과: 짧은 입력 뒤 `5,852 bytes`, 최대 입력 뒤 `7,668 bytes`로 달라져 의도대로 실패했다.
- 기존 기준선도 `default/standard/2` Engine이 case에 따라 `5,724 bytes`와 `7,668 bytes`를
  기록하고 있어 일관성 검사가 실패했다.
- 체크포인트: `a903f7c test: benchmark retained memory 격리 계약 추가`

### GREEN

- retained memory tracing 직전에 full GC를 실행해 이전 workload의 allocator/free-list 상태를
  정리한다. GC 자체 allocation은 tracing 시작 전에 끝나며 latency 표본에도 포함되지 않는다.
- 기준선이 CPython 3.11.9·Windows·warmup 10회·측정 100회인지 검증하고, 같은 Engine 정의의
  retained memory가 모든 case에서 같은지도 검증한다.
- 기준선을 재생성한 결과 `default/standard/2`는 모두 `8,580 bytes`,
  `whitespace-gap/standard/2`는 모두 `11,428 bytes`를 기록했다.
- 체크포인트: `c42a568 fix: benchmark retained memory 측정 격리`

### 추가 Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 15 | 같은 Engine의 retained memory는 앞선 `check()` workload와 무관하다 | `test_retained_memory_is_invariant_to_prior_check_workload` | integration | PASS |
| 16 | Windows 기준선의 런타임·측정 설정과 Engine별 retained memory가 일관된다 | `test_windows_baseline_matches_ordered_complete_corpus_cases` | integration | PASS |
