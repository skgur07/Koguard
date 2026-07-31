# 혼합 공백·구분자 매칭 TDD 증거

## 사용자 시나리오

`시발`을 `시 * 발`처럼 공백·탭과 설정된 특수문자를 함께 삽입해도 탐지해야 한다. 기존
공백 매칭의 opt-in 정책, 부분 토큰 오탐 방지, 원문 span, Whitelist 범위와 매치 우선순위는
그대로 유지해야 한다.

## 범위와 정책

- 기존 `EngineConfig.whitespace_gap_matching=True`일 때만 Mixed 매칭을 활성화한다.
- ASCII 공백·탭에는 기존 `max_whitespace_gap`을 적용한다.
- 특수문자는 기존 `obfuscation_separators`에 포함된 문자만 제거한다.
- 후보 안에서 공백·탭과 구분자를 모두 사용한 경우에만 `MatchMethod.MIXED`로 반환한다.
- 매칭 우선순위는 Exact, Repeated, Separator, Whitespace, Mixed 순서다.
- Mixed 형태의 Whitelist를 자동 생성하지 않고 기존 view에서 실제로 겹치는 원문 구간만
  보호한다.
- 반복 축약과 Mixed view의 조합은 이번 범위에 포함하지 않는다.

## RED

- 대상: `tests/test_models.py`, `tests/test_matcher.py`, `tests/test_engine.py`
- 핵심 계약: 공개 method 값, 전체 원문 span, opt-in, 경계 오탐, 허용 구분자, 줄바꿈과
  간격 상한, Whitelist, longest-first fallback, 최대 4,096자 계산량
- 최초 결과: Mixed API와 method가 없어 신규 계약이 실패
- 체크포인트:
  - `0ab86c6 test: 혼합 공백과 구분자 우회 계약 추가`
  - `f47cb2d test: 혼합 우회 경계와 최대입력 계약 보강`
  - `f58e3d5 test: 혼합 projection 선형 접근 계약 추가`

## GREEN

- 정규화 입력을 선형으로 한 번 projection해 허용된 공백·탭과 구분자를 제거한다.
- 각 projection 경계에 공백과 구분자 사용 누적값을 기록해 후보 판정을 상수 시간에 수행한다.
- 제거하지 않은 원본 정규화 위치로 양끝 토큰 경계를 판정하므로 `시 * 발표`와 `도시 * 발`은
  거부하면서 보호·겹침 때문에 짧은 후보로 돌아가는 동작은 유지한다.
- projection의 source span으로 `matched_text`, `start`, `end`를 원문에 매핑한다.
- Mixed 전용 reversed Aho-Corasick 인덱스를 엔진 생성 시 한 번 만들고, 시작점마다 최장 후보
  하나만 heap에 넣는다. 보호되거나 겹친 후보는 automaton fallback chain에서만 줄인다.
- 기능이 꺼져 있으면 Mixed 인덱스를 만들지 않고 런타임 경로도 실행하지 않는다.
- 구현 체크포인트: `7a4d477 feat: 혼합 공백과 구분자 우회 탐지 추가`

## 성능 확인

Windows, CPython 3.11.9에서 고정 benchmark corpus를 warmup 10회 후 100회 측정했다.

| 입력 | p50 | p95 | peak allocation |
| --- | ---: | ---: | ---: |
| `시 * 발` | 0.0499 ms | 0.0758 ms | 2,082 bytes |
| `시 * 발표` | 0.0428 ms | 0.0515 ms | 1,471 bytes |
| 깊은 공통 접두사 256개와 Mixed 최대 입력 4,096자 | 15.1055 ms | 20.0955 ms | 777,214 bytes |

최대 입력 테스트는 정규화 입력 문자 접근을 길이의 두 배 이하로 제한하고, 최초 후보
materialization도 입력 길이 이하로 고정한다. benchmark의 기대 매치 수가 다르면 성능 결과를
기록하지 않는다.

## 독립 리뷰 수정 RED/GREEN

- P1 RED: 상위 Exact와 겹친 긴 Mixed 후보가 먼저 선택되면서 뒤쪽의 비중첩 Mixed 후보까지
  사라졌다.
- P1 GREEN: Mixed 선택 전에 Exact, Repeated, Separator, Whitespace를 우선순위대로 병합하고,
  실제 점유 원문 mask를 Mixed 선택에 주입해 긴 후보를 건너뛴 뒤 뒤쪽 후보를 보존한다.
- P2 RED: 시작점의 최장 후보가 토큰 끝 경계에서 탈락하면 같은 시작점의 짧은 유효 후보를
  검사하지 않았다.
- P2 GREEN: 최초 후보도 reversed automaton fallback chain을 따라 가장 긴 유효 Mixed
  후보까지 내려간다.
- RED 체크포인트: `67c2d54 test: 혼합 매처 우선순위 fallback 회귀 재현`
- GREEN 체크포인트: `b75a9c9 fix: 혼합 매처 우선순위 fallback 보존`
- 성능 RED: 혼합 gap을 쓰지 않는 최대 입력과 깊은 공통 접두사에서 불가능한 shorter
  fallback을 1,014,912회 검사했다.
- 성능 GREEN: 시작 경계와 gap 사용 여부는 shorter 후보에서 회복될 수 없으므로 즉시
  중단하고, 달라질 수 있는 끝 경계만 fallback한다. 같은 재현의 fallback은 256회로 줄었다.
- 성능 RED 체크포인트: `6f5b3fe test: 혼합 fallback 계산량 폭증 재현`
- 성능 GREEN 체크포인트: `38ce433 fix: 불가능한 혼합 fallback 조기 중단`
- 최종 독립 재리뷰와 27,199개 무작위 oracle 비교에서 추가 finding이나 결과 불일치가 없었다.

## 최종 검증

- `uv sync --all-extras --dev`: PASS
- Ruff format check: 프로젝트 소스·테스트·benchmark 22개 파일 PASS
- Ruff lint: PASS
- mypy strict: 22 source files PASS
- pytest: `161 passed`, branch coverage `95.81%`
- benchmark: 14개 case, warmup 10회·측정 100회 PASS
- build: sdist와 wheel 생성 PASS

## Test specification

| # | 보장 동작 | 테스트 | 유형 |
| --- | --- | --- | --- |
| 1 | `mixed` 공개 method 값을 안정적으로 제공한다 | `test_mixed_match_method_has_stable_public_value` | unit |
| 2 | 공백·탭과 구분자를 섞은 표현의 전체 원문 span을 반환한다 | `test_mixed_gap_matcher_returns_full_original_span` | unit |
| 3 | 기본 설정에서는 Mixed 매칭을 실행하지 않는다 | `test_mixed_gap_matching_is_opt_in` | integration |
| 4 | 부분 영숫자 토큰, 미설정 구분자, 줄바꿈, 간격 초과를 거부한다 | `test_mixed_gap_matching_rejects_invalid_gaps_and_partial_tokens` | integration |
| 5 | Whitelist 형태를 확장하지 않고 실제 겹치는 구간만 보호한다 | `test_exact_whitelist_span_protects_mixed_gap_match` | integration |
| 6 | 보호·겹침 뒤에도 가능한 짧은 후보를 결정적으로 보존한다 | `test_mixed_gap_matching_keeps_shorter_candidate_after_longer_overlap` | integration |
| 7 | 최대 입력과 깊은 공통 접두사에서 후보와 시간 예산을 지킨다 | `test_mixed_gap_matching_bounds_deep_shared_prefix_work` | integration |
| 8 | projection은 최대 입력을 제한된 횟수만 읽는다 | `test_mixed_gap_matcher_reads_maximum_input_a_bounded_number_of_times` | unit |
| 9 | 경계가 없는 최장 후보 대신 짧은 유효 후보로 내려간다 | `test_mixed_gap_matching_falls_back_when_longest_candidate_has_no_token_boundary` | integration |
| 10 | 상위 Exact가 긴 Mixed 후보를 제거해도 뒤쪽 비중첩 후보를 보존한다 | `test_exact_priority_does_not_hide_non_overlapping_mixed_fallback` | integration |
| 11 | 혼합 gap이 없는 shared-prefix 시작점의 불가능한 fallback을 제한한다 | `test_mixed_gap_matcher_skips_impossible_shared_prefix_fallbacks` | unit |

## 알려진 제한

- 보수적인 토큰 경계 정책 때문에 욕설 뒤에 영숫자 접미사가 바로 붙은 표현은 탐지하지 않는다.
- `시이이 * 발`처럼 반복 축약과 Mixed 매칭을 동시에 요구하는 입력은 별도 정책과 계산량
  계약을 정한 뒤 지원한다.
- Mixed 사전 항목은 두 글자 이상의 영숫자 표현으로 제한한다. 구분자 자체가 사전 표현의
  일부인 경우는 기존 Exact 또는 Separator 단계에서 처리한다.
