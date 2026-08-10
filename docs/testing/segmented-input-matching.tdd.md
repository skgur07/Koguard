# 분리 초성·자모·자판 조합 우회 탐지 TDD 증거

## 사용자 여정

- 사용자는 `ㅅ ㅂ`, `ㅅ*ㅂ`처럼 분리된 초성 욕설도 탐지할 수 있다.
- 사용자는 `ㅅㅣ ㅂㅏㄹ`처럼 나뉜 호환 자모와 `tl * qkf`처럼 나뉜 영문 두벌식 입력도
  탐지할 수 있다.
- 운영자는 조합 우회만 `segmented_input_matching=False`로 끄면서 연속 입력 탐지는 유지할
  수 있다.
- 정상 문장과 잘못된 gap을 임의 결합하지 않고 Whitelist와 원문 span을 보존한다.

## 설계 경계

- 공백을 전역 제거하지 않고 양쪽 문자가 같은 입력 체계에 속할 때만 projection에서 제거한다.
- 설정된 `obfuscation_separators`와 `max_whitespace_gap`을 재사용한다.
- 줄바꿈, 설정되지 않은 구분자, 초과 공백, 부분 영숫자 토큰은 결합하지 않는다.
- 새 플래그와 기존 입력 체계별 플래그가 모두 `True`일 때만 해당 조합 우회를 실행한다.
- 결과 method는 기존 `CHOSEONG`, `JAMO`, `KEYBOARD`를 유지한다.

## RED

- 핵심 명령:
  `uv run pytest tests/test_segmented_input_matching.py tests/test_normalizer.py tests/test_config.py tests/test_corpus.py --no-cov -q`
- 결과: 새 설정과 세 projection 부재로 `24 failed, 96 passed`
- 체크포인트: `457f6c5 test: 조합 우회 입력 탐지 계약 추가`
- 성능 명령: `uv run pytest tests/test_benchmark.py --no-cov -q`
- 결과: benchmark profile과 저장 기준선 부재로 `3 failed, 17 passed`
- 체크포인트: `dfe0468 test: 조합 우회 탐지 성능 계약 추가`

## GREEN

- 핵심 명령:
  `uv run pytest tests/test_segmented_input_matching.py tests/test_normalizer.py tests/test_config.py tests/test_corpus.py tests/test_keyboard_input_matching.py --no-cov -q`
- 결과: `128 passed`
- 전체 회귀 중간 확인: `350 passed`
- 체크포인트: `0cd0901 feat: 분리 초성·자모·자판 입력 탐지 추가`
- benchmark profile 검증: `20 passed`
- 최종 리뷰 RED: 자모 조합을 끈 분리 초성 테스트 `1 failed`
- 회귀 체크포인트: `661cfbb test: 분리 초성 설정 독립성 회귀 추가`
- 수정 GREEN: 관련 설정·성능 테스트 `55 passed`
- 수정 체크포인트: `8619737 fix: 분리 초성의 자모 설정 의존성 제거`

## 전체 검증

- `uv run ruff format --check .`: 25개 파일 통과
- `uv run ruff check .`: 통과
- `uv run mypy`: 25개 source file, 오류 없음
- `uv run pytest`: `353 passed`, branch coverage `95.61%`
- `uv build`: wheel과 sdist 생성 성공

## 테스트 명세

| # | 보장 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 세 입력 체계의 분리 표현을 canonical term과 원문 span으로 반환한다 | `test_segmented_input_detects_profanity_with_original_span` | 통합 | PASS |
| 2 | 조합 우회 플래그를 독립적으로 끌 수 있다 | `test_segmented_input_matching_can_be_disabled` | 통합 | PASS |
| 3 | 기존 입력 체계별 플래그를 존중한다 | `test_segmented_input_respects_base_matcher_flags` | 통합 | PASS |
| 4 | 정상·부분 토큰을 결합하지 않는다 | `test_segmented_input_does_not_join_partial_or_unrelated_tokens` | 통합 | PASS |
| 5 | 잘못된 gap과 줄바꿈을 거부한다 | `test_segmented_input_rejects_unconfigured_or_invalid_gaps` | 통합 | PASS |
| 6 | 변환된 Whitelist와 원문 span을 보존한다 | `test_segmented_input_honors_transformed_whitelist` | 통합 | PASS |
| 7 | 9문장 corpus에서 FP/FN이 없다 | `test_segmented_input_corpus_has_no_false_positives_or_false_negatives` | corpus | PASS |
| 8 | 짧은 세 유형과 4,096자 입력의 성능을 기록한다 | `test_windows_baseline_matches_ordered_complete_corpus_cases` | 성능 | PASS |

## 성능 기준선

Windows, CPython 3.11.9, 100 iterations, 10 warmups에서 측정했다.

| 입력 | p50 | p95 |
| --- | ---: | ---: |
| `ㅅ * ㅂ` | 0.0962 ms | 0.1015 ms |
| `ㅅㅣ ㅂㅏㄹ` | 0.0978 ms | 0.1123 ms |
| `tl * qkf` | 0.0746 ms | 0.0845 ms |
| 4,096자 조합 입력 | 13.0777 ms | 13.4544 ms |

## 알려진 제한

- 세벌식과 일반 로마자 표기법은 지원하지 않는다.
- 조합 우회는 규칙 기반이므로 사전에 없는 신조어와 문맥적 모욕을 일반화하지 않는다.
- 짧은 수동 corpus의 정확도는 실제 서비스 분포를 대표하지 않는다.
