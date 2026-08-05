# MIT Korcen 기반 기본 사전 확장 TDD 증거

## 사용자 여정

기본 엔진 사용자는 별도의 사전을 구성하지 않아도 `개자식`, `뒤져`, `느그애미`,
`빡대가리` 같은 대표 욕설·모욕 표현을 탐지하고, 배포된 각 항목의 출처와 라이선스를
확인할 수 있어야 한다.

## 데이터 경계

- 원본: https://github.com/Tanat05/korcen
- 고정 revision: `eecd9763dbdccce3dc96ddb578ef0b6396058fa9`
- 라이선스: MIT, `src/koguard/data/KORCEN-MIT.txt`에 보존
- 선별 범위: `GENERAL`, `MINOR`, `BELITTLE`, `PARENT` 패턴의 명시적 표현
- 제외: 라이선스가 확인되지 않은 `korean-profanity-resources/slang.csv`

짧고 중의적인 단독 표현, 정치·정체성 표현, 성적 표현군은 기본 정책의 오탐 위험 때문에
이번 확장에서 제외했다.

## RED

- 테스트: `tests/test_dictionary.py`, `tests/test_corpus.py`,
  `tests/corpus/exact_cases.json`
- 명령: `uv run pytest tests/test_dictionary.py tests/test_corpus.py --no-cov -q`
- 결과: 기본 항목과 라이선스 파일 부재로 `3 failed, 15 passed`
- 체크포인트: `754c338 test: MIT 사전 확장 계약 추가`

## GREEN

- 기본 blacklist에 MIT Korcen에서 선별한 26개 표현 추가
- 원본 revision, 변환 방식, 제외한 데이터의 경계를 `NOTICE.md`에 기록
- Korcen의 MIT 라이선스와 저작권 고지를 배포 데이터에 포함
- 명령: `uv run pytest tests/test_dictionary.py tests/test_corpus.py --no-cov -q`
- 결과: `18 passed`

## 전체 검증

- `uv run ruff format --check .`: 통과
- `uv run ruff check .`: 통과
- `uv run mypy`: 24개 source file, 오류 없음
- `uv run pytest`: `310 passed`, branch coverage `95.59%`
- `uv build`: wheel과 sdist 생성 성공, 두 배포물에서 `NOTICE.md`와
  `KORCEN-MIT.txt` 포함 확인

## 보장 동작

| # | 보장 내용 | 검증 |
| --- | --- | --- |
| 1 | 대표 Korcen 선별 표현과 최소 50개 기본 표현을 포함한다 | `test_default_dictionary_loads_bundled_terms` |
| 2 | 원본 URL과 고정 revision을 고지한다 | `test_packaged_korcen_terms_include_pinned_mit_notice` |
| 3 | MIT 라이선스와 저작권 표시를 보존한다 | `test_packaged_korcen_terms_include_pinned_mit_notice` |
| 4 | 확장된 Exact Match corpus에서 FP/FN이 없다 | `test_exact_corpus_has_no_false_positives_or_false_negatives` |

## 알려진 제한

기본 탐지는 문맥을 해석하지 않는 substring Exact Match다. 선별 표현의 철자 변형과 새로운
은어를 자동 일반화하지 않으며, 실제 서비스에서는 사용자 정책에 맞는 Whitelist와 운영
corpus를 함께 관리해야 한다.
