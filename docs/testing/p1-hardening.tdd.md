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
- `4cb8cf5 test: 전역 Whitelist와 Trie 최악 경로 재현`
- `58f7207 test: 조밀한 Exact 접두사 선형 탐색 계약 추가`

재현 결과:

| 문제 | RED 증거 |
| --- | --- |
| Unicode cluster | 4,096자 결합문자의 누적 정규화 입력량 `8,390,656 > 8,192` |
| Exact 후보 | 512자·128개 공통 접두사에서 후보 매핑 `57,280 > 2,048` |
| 장문 단일 term | 가능한 시작점은 1개지만 finder를 4,096회 호출 |
| View Whitelist | `ab-cd`에서 보호돼야 할 Exact 하위 term `ab`가 반환됨 |
| 전역 Whitelist fallback | 다른 view에서 보호된 최장 후보가 제거된 뒤 같은 시작점의 짧은 후보도 유실됨 |
| 짧고 긴 접두사 | `["a", "a" * 4,096]`에서 문자 접근 `8,394,752 > 16,384` |
| 조밀한 접두사 | 512개 접두사와 512자 입력에서 문자 접근 `131,840 > 4,096` |
| Whitelist 열거 | 128개 겹치는 Whitelist와 512자 입력에서 후보 매핑 `115,072 > 1,024` |
| sdist | `/benchmarks`가 include 목록에 없어 benchmark 테스트의 import 대상이 누락됨 |

## GREEN

체크포인트:

- `23b5827 fix: Unicode 정규화 계산량 상한 보장`
- `a5d98d8 fix: 매처 계산량과 Whitelist 보호 강화`
- `97b6c41 fix: sdist에 benchmark 하네스 포함`
- `23bbc5d fix: 매처 최악 계산량과 전역 Whitelist fallback 해결`

구현:

- Unicode cluster를 한 번 정규화하고 decomposition provenance로 원문 span을 선형 매핑한다.
- 역방향 Aho-Corasick automaton으로 Exact 입력을 한 번 스캔해 시작점별 최장 후보만 만든다.
- failure output chain으로 같은 시작점의 짧은 후보를 입력 재스캔 없이 찾는다.
- Whitelist도 시작점별 최장 occurrence만 매핑해 같은 시작점의 모든 짧은 보호 구간을 합친다.
- Exact, repeated, separator view별 Whitelist mask를 한 번만 만들고 원문 mask를 합친 뒤,
  각 matcher의 후보 선택과 최종 병합에 동일하게 적용한다.
- 공백 matcher는 Whitelist 공백을 확장하지 않으면서도 다른 view의 전역 원문 보호 구간을
  후보 선택에 적용한다.
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
| 7 | 짧고 긴 term이 같은 접두사를 가져도 입력 문자 접근이 선형 상한 안에 든다 | `test_exact_matcher_bounds_character_reads_with_short_and_long_term` | unit | PASS |
| 8 | 조밀한 접두사 사전도 입력 문자 접근이 선형 상한 안에 든다 | `test_exact_matcher_bounds_character_reads_with_dense_prefix_terms` | unit | PASS |
| 9 | 전역 보호가 최장 후보만 막으면 같은 시작점의 짧은 Exact 후보를 반환한다 | `test_global_whitelist_falls_back_to_shorter_exact_candidate` | integration | PASS |
| 10 | 전역 보호가 최장 후보만 막으면 짧은 공백 후보를 반환한다 | `test_global_whitelist_falls_back_to_shorter_whitespace_candidate` | integration | PASS |
| 11 | 겹치는 Whitelist를 view마다 중복 열거하지 않는다 | `test_engine_bounds_overlapping_whitelist_mapping_and_reuses_view_mask` | integration | PASS |

## Verification

- 관련 matcher·engine GREEN: `51 passed`
- 전체 테스트: `136 passed`
- branch coverage: `96.17%` (`fail_under = 90`)
- Ruff format: 추적 대상 `src`, `tests`, `benchmarks` 통과
- Ruff lint: 통과
- mypy strict: 22개 source file 통과
- build: wheel과 sdist 생성 성공
- 최종 sdist: `benchmarks/engine_benchmark.py`, `tests/test_benchmark.py` 포함 및
  `136 tests collected`
- benchmark 11 cases: 정확도 기대값 전부 통과
- `overlapping-prefix-512`: p50 `10.4996ms → 3.3775ms`, peak allocation
  `880,165 → 143,182 bytes`
- `["a", "a" * 4,096]`: 약 `867ms → 24.452ms`
- 조밀한 접두사 512개: 약 `2.524ms`
- 겹치는 Whitelist 128개와 4,096자 입력: 약 `2.13s → 12.51ms`
- 최대 결합문자 cluster: 약 `1.87s → 9.1ms`
- 기존 완전열거 참조와 ASCII·Unicode 30,000건, 독립 리뷰 oracle의 변환 view와
  전역 mask 경로 21,000건 대조에서 결과 불일치 없음

## Known gaps

- 혼합 공백·특수문자 우회는 P2 후속 범위다.
- 공개 배포 라이선스는 소유자가 선택해야 하므로 이번 변경에 포함하지 않았다.
- 미추적 `test.py` 때문에 저장소 루트 전체 format check만 실패하며 추적 소스에는 영향이 없다.
- `pip-audit`는 개발 환경에 설치되어 있지 않다. core runtime dependency는 없다.
