# 공백 간격 매칭 TDD 증거

## 사용자 시나리오

사전의 욕설 글자 사이에 짧은 공백이나 탭을 삽입한 우회 표현을 탐지하되, 정상 단어의 일부를
욕설로 잘못 판단하지 않아야 한다. 탐지 결과는 공백을 포함한 원문 구간을 보존하고 기존 Exact,
Repeated, Separator 및 Whitelist 동작을 유지해야 한다.

## 범위와 정책

- `EngineConfig.whitespace_gap_matching`은 기본값이 `False`인 opt-in 기능이다.
- `max_whitespace_gap`은 각 글자 사이에서 허용할 최대 공백 문자 수이며 기본값은 3이다.
- ASCII 공백과 탭만 허용하고 줄바꿈과 다른 Unicode 공백은 허용하지 않는다.
- 사전 단어 자체에 공백이 있는 항목은 기존 Exact Match가 처리한다.
- 공백을 사용한 후보의 양끝이 영숫자 토큰 중간이면 후보를 버린다.
- 매칭 우선순위는 Exact, Repeated, Separator, Whitespace 순서다.
- 공백 매치는 `MatchMethod.WHITESPACE`로 구분한다.

## RED

- 대상: `tests/test_config.py`, `tests/test_matcher.py`, `tests/test_engine.py`
- 명령:
  `.venv\Scripts\python.exe -m pytest tests/test_config.py tests/test_matcher.py tests/test_engine.py -q`
- 결과: 신규 설정과 매칭 API가 없어 `19 failed, 42 passed`
- 체크포인트: `f124107 test: 공백 간격 매칭 계약 추가`

## GREEN

- 공백 매칭 전용 Trie를 엔진 초기화 시 한 번 구성하고, 정규화된 입력을 따라가며 각 글자
  사이의 공백 구간만 제한적으로 허용한다.
- 정규화 단계가 보존한 source span으로 원문의 공백 종류와 길이를 검증한다.
- 기존 Whitelist 마스크와 비중첩 선택 로직을 공백 후보에도 동일하게 적용한다.
- 엔진에서 기능이 활성화된 경우에만 Whitespace 후보를 계산하고 마지막 우선순위로 병합한다.
- `tests/corpus/whitespace_gap_cases.json`에서 긍정·오탐 방지 사례의 precision과 recall을
  각각 1.0으로 고정한다.
- 전체 테스트 명령: `.venv\Scripts\python.exe -m pytest -q`
- 최초 GREEN 결과: `114 passed`, 전체 branch coverage `97.28%`

## 성능 확인

기본 사전과 최대 입력 길이 4,096자를 사용해 각 입력을 100회 검사했다. 공백 기능을 끈 경우와
켠 경우를 같은 프로세스에서 비교했으며, 공백 후보가 반복되는 입력은 별도로 50회 측정했다.

| 입력 | 기능 비활성 | 기능 활성 |
| --- | ---: | ---: |
| 정상 문장 4,096자 | 2.219 ms/check | 2.442 ms/check |
| `시 ` 반복 4,096자 | 2.210 ms/check | 3.981 ms/check |
| `시 발 ` 반복 4,096자, 1,024매치 | - | 9.433 ms/check |
| 공통 접두사 사전 1,000개와 후보 반복 4,096자 | - | 4.381 ms/check |

기능이 꺼진 기본 경로는 조건 분기만 추가한다. 기능을 켠 최악 후보 입력도 현재 최대 입력 길이와
기본 사전에서 한 번의 검사가 10 ms 이내였다. 사전 1,000개가 같은 접두사를 공유하는 입력은
term별 스캔에서 약 1,916.623 ms가 걸렸으나 Trie 스캔으로 바꾼 뒤 4.381 ms로 줄었다. 기능이
꺼지면 Trie를 구성하지 않으며, 별도 캐시나 런타임 네트워크 의존성도 추가하지 않았다.

## 최종 검증

- Ruff format check: 22 files formatted
- Ruff lint: PASS
- mypy strict: 22 source files PASS
- pytest: `115 passed`, branch coverage `97.39%`
- build: sdist와 wheel 생성 PASS

## Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 기본 설정에서는 기존 동작을 유지한다 | `test_whitespace_gap_matching_is_opt_in` | integration | PASS |
| 2 | 공백·탭 삽입 표현과 전체 원문 span을 반환한다 | `test_whitespace_gap_matcher_returns_full_original_span` | unit | PASS |
| 3 | `시 발표`, `도시 발` 같은 부분 토큰 후보를 거부한다 | `test_whitespace_gap_matcher_rejects_partial_alphanumeric_tokens` | unit | PASS |
| 4 | 최대 간격을 초과하거나 줄바꿈이 포함된 후보를 거부한다 | `test_whitespace_gap_matching_respects_gap_limit_and_rejects_line_breaks` | integration | PASS |
| 5 | Whitelist는 겹치는 공백 후보 구간만 보호한다 | `test_whitespace_gap_matcher_applies_whitelist_to_only_overlapping_span` | unit | PASS |
| 6 | Exact와 Whitespace 결과를 원문 순서로 함께 보존한다 | `test_exact_and_whitespace_gap_matches_are_both_preserved` | integration | PASS |

## 알려진 제한

- 보수적인 토큰 경계 규칙 때문에 `시 발놈`처럼 욕설 뒤에 접미 표현을 바로 붙인 입력은 현재
  탐지하지 않는다. 접미 표현 사전이나 형태소 경계 정책을 별도로 정의한 뒤 확장한다.
- 공백과 특수문자를 동시에 섞은 `시 * 발`은 view를 합성하지 않으므로 현재 탐지하지 않는다.
  합성 view는 정확도 corpus와 계산량 상한을 먼저 정의한 뒤 검토한다.
