# P1 hardening TDD 증거

## Source

별도 계획 파일 없이 2026-07-30 코드 감사에서 확인한 P1 네 건을 사용자 여정과 회귀
계약으로 변환했다.

- 외부 입력을 검사하는 서비스는 허용 길이의 Unicode 입력으로 CPU가 고갈되지 않아야 한다.
- 큰 사용자 사전을 쓰는 서비스는 겹치는 Exact 후보 때문에 메모리와 시간이 폭증하지 않아야 한다.
- Whitelist로 보호된 원문 구간은 어느 정규화 view에서 발견됐는지와 무관하게 보호되어야 한다.
- 소스 배포물을 검증하는 사용자는 함께 배포된 테스트를 누락된 모듈 없이 수집할 수 있어야 한다.

## RED

체크포인트:

- `f7c4216 test: P1 계산량과 Whitelist 회귀 재현`
- `0c7d3f5 test: 장문 단일 사전어 탐색 회귀 재현`

재현 결과:

| 문제 | RED 증거 |
| --- | --- |
| Unicode cluster | 4,096자 결합문자의 누적 정규화 입력량 `8,390,656 > 8,192` |
| Exact 후보 | 512자·128개 공통 접두사에서 후보 매핑 `57,280 > 2,048` |
| 장문 단일 term | 가능한 시작점은 1개지만 finder를 4,096회 호출 |
| View Whitelist | `ab-cd`에서 보호돼야 할 Exact 하위 term `ab`가 반환됨 |
| sdist | `/benchmarks`가 include 목록에 없어 benchmark 테스트의 import 대상이 누락됨 |

## GREEN

체크포인트:

- `23b5827 fix: Unicode 정규화 계산량 상한 보장`
- `a5d98d8 fix: 매처 계산량과 Whitelist 보호 강화`
- `97b6c41 fix: sdist에 benchmark 하네스 포함`

구현:

- Unicode cluster를 한 번 정규화하고 decomposition provenance로 원문 span을 선형 매핑한다.
- Exact Trie에서 시작점별 최장 후보만 heap에 유지하고 충돌할 때만 짧은 후보를 찾는다.
- 남은 입력보다 첫 terminal 길이가 길면 Exact 탐색을 시작하지 않는다.
- Exact, repeated, separator view의 Whitelist 원문 mask를 최종 병합에 함께 적용한다.
- sdist에 `benchmarks/`를 포함한다.

## Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 최대 결합문자 cluster의 정규화 작업량이 입력 길이에 비례한다 | `test_normalizer_processes_max_length_combining_cluster_with_linear_work` | unit | PASS |
| 2 | canonical reorder 후에도 모든 span이 원문 방향과 기여 문자를 보존한다 | `test_normalizer_reordered_combining_spans_cover_each_source_character` | unit | PASS |
| 3 | 공통 접두사 Exact 후보가 제한되고 결과가 결정적이다 | `test_exact_matcher_bounds_candidates_and_keeps_deterministic_results` | unit | PASS |
| 4 | 장문 단일 term에서 불가능한 시작점을 탐색하지 않는다 | `test_exact_matcher_skips_starts_too_short_for_single_long_term` | unit | PASS |
| 5 | Separator view Whitelist가 겹치는 Exact view 매치도 보호한다 | `test_separator_view_whitelist_protects_overlapping_exact_view_match` | integration | PASS |
| 6 | sdist가 함께 배포한 benchmark 테스트의 import 대상을 포함한다 | `test_sdist_includes_benchmark_harness_used_by_packaged_tests` | packaging | PASS |

## Verification

- 관련 GREEN: `6 passed`
- 전체 테스트: `131 passed`
- branch coverage: `96.02%` (`fail_under = 90`)
- Ruff format: 추적 대상 `src`, `tests`, `benchmarks` 통과
- Ruff lint: 통과
- mypy strict: 22개 source file 통과
- build: wheel과 sdist 생성 성공
- 최종 sdist: `benchmarks/engine_benchmark.py`, `tests/test_benchmark.py` 포함 및
  `131 tests collected`
- benchmark 11 cases: 정확도 기대값 전부 통과
- `overlapping-prefix-512`: p50 `10.4996ms → 3.2068ms`, peak allocation
  `880,165 → 142,902 bytes`
- 최대 결합문자 cluster: 약 `1.87s → 9.1ms`

## Known gaps

- 혼합 공백·특수문자 우회는 P2 후속 범위다.
- 공개 배포 라이선스는 소유자가 선택해야 하므로 이번 변경에 포함하지 않았다.
- 미추적 `test.py` 때문에 저장소 루트 전체 format check만 실패하며 추적 소스에는 영향이 없다.
- `pip-audit`는 개발 환경에 설치되어 있지 않다. core runtime dependency는 없다.
