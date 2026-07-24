# Trie matcher TDD 증거

## Source plan

- [Phase 2 — v0.2 Normalizer + Trie + Benchmark](../implementation-plan.md)
- 이번 작업 범위는 `longest-match-first Trie 구현`으로 제한했다.

## User journey

사전 기반 탐지를 사용하는 개발자로서, 공통 접두사를 가진 여러 금칙어를 Trie로 탐색하면서도
기존의 longest-match, 원문 span, Whitelist 동작을 그대로 유지하고 싶다.

## Task report

### RED

- 테스트: `tests/test_matcher.py`
- 명령: `uv run pytest tests/test_matcher.py`
- 결과: `TrieMatcher`가 구현되지 않아 import 단계에서 의도대로 실패
- 체크포인트: `2157cef test: Trie matcher 동작 계약 추가`

### GREEN

- 구현: blacklist와 whitelist를 각각 prefix Trie로 구성하고 입력의 각 시작 위치에서 후보 탐색
- Engine 연결: 기존 사전 순회 matcher를 `TrieMatcher`로 교체
- 명령: `uv run pytest --no-cov tests/test_matcher.py tests/test_engine.py tests/test_corpus.py`
- 결과: `18 passed`
- 전체 명령: `uv run pytest`
- 결과: `63 passed`, total coverage `98.78%`
- 체크포인트: `6e7c180 feat: Trie 기반 exact matcher 구현`

## Test specification

| # | 보장 동작 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | 공통 접두사 후보 중 가장 긴 매치를 선택한다 | `test_trie_matcher_prefers_longest_shared_prefix_and_keeps_later_match` | unit | PASS |
| 2 | 떨어진 유효 매치는 함께 반환한다 | 같은 테스트의 `금칙`, `욕설` 결과 | unit | PASS |
| 3 | Whitelist는 겹치는 후보만 제거한다 | `test_trie_matcher_applies_whitelist_to_only_overlapping_span` | unit | PASS |
| 4 | 기존 Engine·corpus 계약을 보존한다 | `tests/test_engine.py`, `tests/test_corpus.py` | integration | PASS |

## Coverage and known gaps

- 전체 branch coverage 기준 90%를 통과했으며 측정 결과는 98.78%다.
- 이번 범위에는 benchmark baseline과 반복 문자·특수문자·자판·초성 view가 포함되지 않는다.
- Trie는 Engine 생성 시 한 번 구성되고 이후 읽기 전용으로 사용한다.
