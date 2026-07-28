# 특수문자 삽입 우회 탐지 TDD 증거

## 사용자 여정

사전 기반 탐지를 사용하는 운영자로서 `시*!발`처럼 문자 사이에 기호를 넣어 우회한 표현을
탐지하면서도 원문 span, Exact 우선순위, 사용자 Whitelist를 유지하고 싶다.

## 범위와 정책

- `EngineConfig.obfuscation_separators`에 명시한 한 글자 기호만 제거한다.
- 기호가 영숫자 사이에 있을 때만 별도 view에서 제거한다.
- 공백, 영숫자, 설정하지 않은 기호는 제거하지 않는다.
- 기본 view를 변경하지 않으며 Exact, Repeated, Separator 순서로 겹치는 구간의 우선순위를
  결정한다.
- 특수문자 view 매치는 `MatchMethod.SEPARATOR`로 구분한다.

## RED

- 테스트: `tests/test_config.py`, `tests/test_normalizer.py`, `tests/test_engine.py`,
  `tests/test_corpus.py`
- 명령:
  `uv run pytest tests/test_normalizer.py tests/test_engine.py tests/test_config.py tests/test_corpus.py -q`
- 결과: `build_separator_view`가 없어 import 단계에서 의도대로 실패
- 체크포인트: `ad38789 test: 특수문자 삽입 우회 탐지 계약 추가`

## GREEN

- 설정 가능한 기호 집합과 입력 검증 구현
- 기호 run을 제거하면서 앞 문자의 source span을 확장해 원문 전체 구간 보존
- Exact·Repeated·Separator 결과를 원문 구간 기준으로 통합
- 특수문자 view에도 동일 Whitelist 적용
- 기호가 없는 입력은 집합 교집합 fast path로 기존 view를 즉시 반환
- 명령:
  `uv run pytest tests/test_normalizer.py tests/test_engine.py tests/test_config.py tests/test_corpus.py -q`
- 결과: `56 passed`, 전체 branch coverage `92.01%`
- 체크포인트: `5fb2e12 feat: 특수문자 삽입 우회 탐지 view 추가`

## 성능 리뷰

초기 구현의 Python 제너레이터 fast path는 정상 입력의 p50을 약 16~30% 증가시켰다.
`frozenset.isdisjoint()`로 바꾼 후 동일 장비·100회 측정의 기존 기준선 대비 결과는 다음과
같다.

| case | 기존 | 변경 후 | 배율 |
| --- | ---: | ---: | ---: |
| 1 KB 정상 입력 | 0.5973 ms | 0.6422 ms | 1.08배 |
| 최대 4,096자 | 2.5092 ms | 2.7456 ms | 1.09배 |
| 반복 후보 512자 | 10.3903 ms | 10.0414 ms | 0.97배 |
| 사전 1,000개 | 0.2343 ms | 0.2248 ms | 0.96배 |

짧은 정상 입력은 0.0119 ms에서 0.0148 ms로 증가했지만 절대 증가는 0.0029 ms였다.
특수문자 우회 입력은 benchmark corpus에 별도 category로 추가했다.

## Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 허용된 기호 run을 제거하고 원문 span을 보존한다 | `test_separator_view_removes_allowed_run_between_characters_and_preserves_span` | unit | PASS |
| 2 | 경계·공백·미설정 기호는 제거하지 않는다 | `test_separator_view_keeps_boundaries_whitespace_and_unconfigured_symbols` | unit | PASS |
| 3 | 우회 표현은 `SEPARATOR` 방법과 원문 구간으로 반환된다 | `test_special_character_obfuscation_is_detected_with_original_span` | integration | PASS |
| 4 | 사용자 Whitelist는 특수문자 view에도 적용된다 | `test_whitelist_protects_separator_view_match` | integration | PASS |
| 5 | 잘못된 구분자 설정은 초기화 시 거부된다 | `test_config_rejects_invalid_obfuscation_separators` | unit | PASS |

## 알려진 제한

이 view는 설정된 기호만 제거하며 공백, 자판 입력, 초성 표현, 철자 누락은 처리하지 않는다.
서로 다른 우회 view를 연속 합성하는 동작은 오탐과 계산량 정책을 정한 뒤 별도로 검토한다.

## 리뷰 수정

- 재현: NFKC 설정에서 `obfuscation_separators={"＊"}`를 사용하면 입력은 `시*발`로
  정규화되지만 설정값은 `＊`로 남아 탐지되지 않았다.
- 수정: 구분자 설정도 입력과 동일한 `unicode_form`으로 정규화하고, 정규화 결과가 한 글자의
  비영숫자·비공백 문자인지 검증한다.
- 결과: 전각 `＊` 설정이 내부적으로 `*`가 되며 `시＊발`의 원문 span을 보존해 탐지한다.
- RED 체크포인트: `5a03d16 test: Unicode 구분자 설정 불일치 재현`
