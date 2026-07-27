# Exact matcher 성능 수정 TDD 증거

## 문제와 결정

Python prefix Trie는 입력의 모든 시작 위치를 Python 루프로 순회했고, 다수 후보 입력에서는
Whitelist와 최종 후보가 서로 겹치는지 쌍별로 비교했다. 프로파일 결과 일반 입력은 Unicode
정규화가, 반복 후보 입력은 matcher의 쌍별 비교가 주 병목이었다.

현재의 작은 사전 규모에서는 CPython의 최적화된 `str.find`가 Python Trie보다 빨랐다. 따라서
Trie 시제품을 유지하는 대신 다음 최저 비용 경로를 선택했다.

- term별 겹치는 출현 위치는 `str.find`로 검색
- Whitelist와 선택된 구간은 원문·정규화 위치 마스크로 관리
- ASCII와 완성형 한글 중 결합 문자가 뒤따르지 않는 문자는 Unicode 정규화 호출 생략

원문 span, Whitelist 우선, longest-match-first, 결정적 결과 순서는 변경하지 않았다.

## RED

- 테스트: `tests/test_matcher.py`, `tests/test_normalizer.py`
- matcher 계약: 후보 간 `overlaps()` 호출을 금지하고 반복 접두사 입력 결과를 검증
- normalizer 계약: 안정적인 ASCII·완성형 한글에서 `unicodedata.normalize()` 호출을 금지
- 결과:
  - `ExactMatcher`가 없어 matcher 테스트가 import 단계에서 실패
  - 기존 normalizer가 ASCII 문자에도 정규화를 호출해 실패
- 체크포인트: `4448161 test: matcher 및 정규화 성능 회귀 계약 추가`

## GREEN

- 명령: `uv run pytest --no-cov tests/test_matcher.py tests/test_normalizer.py`
- 결과: `15 passed`
- 정적 검사: Ruff 통과, mypy 19개 소스 파일 통과
- 전체 검증: `65 passed`, branch coverage `97.88%`, wheel·sdist 빌드 성공

## 로컬 기준 측정

환경은 Windows, CPython 3.11.9이며 각 수치는 여러 반복 중 최솟값이다. 절대 성능 보증값이
아니라 동일 작업 전후의 회귀 판단 자료로 사용한다.

| 입력 | 변경 전 | 변경 후 | 개선 |
| --- | ---: | ---: | ---: |
| 일반 32자 | 0.0553 ms | 0.0172 ms | 3.2배 |
| 일반 1,024자 | 1.7367 ms | 0.4750 ms | 3.7배 |
| 일반 4,096자 | 7.1012 ms | 1.9286 ms | 3.7배 |
| 반복 후보 64자 | 1.6788 ms | 1.0841 ms | 1.5배 |
| 반복 후보 256자 | 10.5840 ms | 4.4898 ms | 2.4배 |
| 반복 후보 512자 | 31.0659 ms | 9.2366 ms | 3.4배 |

## 남은 한계

term별 `str.find` 검색은 사전 항목 수에 선형 비례한다. 사전이 크게 성장하면 같은 corpus로
Aho-Corasick 같은 다중 패턴 인덱스를 비교하고, 정확성과 메모리 상한을 함께 검증해야 한다.
