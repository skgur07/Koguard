# 기본 사전과 Whitelist 정책 변경 TDD 증거

## 사용자 여정

기본 정책을 사용하는 운영자로서 `시발점`, `병신년`도 금칙어가 포함된 표현으로 탐지하고,
최소 fixture보다 넓은 기본 욕설 목록을 사용하고 싶다.

외부 데이터셋은 라이선스와 재배포 조건이 검증되지 않았으므로 사용하지 않았다. 기본 항목은
프로젝트에서 직접 선별했으며 출처 정책은 `src/koguard/data/NOTICE.md`에 기록했다.

## RED

- 테스트:
  - `tests/test_dictionary.py`
  - `tests/test_engine.py`
  - `tests/test_corpus.py`
  - `tests/corpus/exact_cases.json`
- 명령:
  `uv run pytest --no-cov tests/test_dictionary.py tests/test_engine.py tests/test_corpus.py`
- 결과: 확장 항목 부재, 기존 Whitelist 보호, corpus 누락으로 `4 failed`
- 체크포인트: `cee52af test: 기본 사전과 whitelist 정책 변경 계약 추가`

## GREEN

- 기본 blacklist: 직접 선별한 35개 Exact Match 항목으로 최초 GREEN
- 기본 whitelist: 항목 없음
- 사용자 whitelist: `KoguardDictionary.from_sources()`를 통한 기존 주입 기능 유지
- 명령:
  `uv run pytest --no-cov tests/test_dictionary.py tests/test_engine.py tests/test_corpus.py`
- 결과: `23 passed`
- 체크포인트: `5b24215 feat: 기본 금칙어 사전과 whitelist 정책 갱신`

## Refactor

substring Exact Match에서 정상 복합어 오탐 가능성이 높은 `새끼`, `졸라`, `애미`, `애비`,
`니미` 단독 항목을 제거했다. 복합 욕설은 유지했고 기본 blacklist는 최종 30개다.
`새끼손가락`, `졸라매다`, `애니미즘`이 탐지되지 않는 corpus case를 추가했다.

## 보장 동작

| # | 보장 내용 | 검증 |
| --- | --- | --- |
| 1 | 기본 blacklist가 대표 확장 항목과 최소 30개 표현을 포함한다 | `test_default_dictionary_loads_bundled_terms` |
| 2 | `시발점`, `병신년` 내부 금칙어를 기본 정책에서 탐지한다 | `test_default_engine_detects_both_former_whitelist_examples` |
| 3 | 한 문장의 별도 매치가 원문 순서로 유지된다 | `test_default_engine_detects_terms_inside_former_whitelist_examples` |
| 4 | 정책 변경 후에도 동시 호출 결과가 일관적이다 | `test_engine_is_safe_for_concurrent_checks` |
| 5 | 확장된 정확도 corpus에서 FP/FN이 없다 | `test_exact_corpus_has_no_false_positives_or_false_negatives` |

## 알려진 제한

현재 기본 사전은 문맥을 해석하지 않는 substring Exact Match다. 짧거나 중의적인 표현은 정상
문장에서도 탐지될 수 있으므로 실제 서비스는 정책에 맞는 사용자 Whitelist와 더 큰 검증
corpus를 함께 운영해야 한다. 리뷰 과정에서 `새끼`, `졸라`, `애미`, `애비`, `니미` 단독
항목은 정상 복합어 오탐 위험 때문에 기본값에서 제외했다.
