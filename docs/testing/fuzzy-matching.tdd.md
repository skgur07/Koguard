# Fuzzy Matching TDD 증거

## 사용자 여정

- 사용자는 한 글자 삽입·삭제·치환이 있는 독립 욕설 토큰을 canonical term으로 탐지할 수 있다.
- 운영자는 Fuzzy를 독립적으로 끄거나 거리, term 길이, check 연산량과 index 크기를 제한할 수
  있다.
- Fuzzy 결과는 원문 span, Whitelist, 상위 규칙 기반 매치와 결정적 순서를 보존한다.

## 설계 경계

- 기본 탐지 범위는 3~32글자, 편집거리 1인 독립 영숫자 토큰이다.
- 1~2글자 term, 토큰 일부, 공백·구분자를 가로지르는 후보는 비교하지 않는다.
- Fuzzy는 모든 Exact·우회 단계 다음의 fallback으로 실행한다.
- score는 `1 - distance / max(len(token), len(term))`으로 계산한다.
- `fuzzy_min_score`로 거리와 별도의 최소 score를 설정할 수 있다.
- check 연산 예산을 초과하면 불완전한 결과를 반환하지 않고 입력을 노출하지 않는 예외를
  발생시킨다.
- 연산 예산은 서명 생성·조회, 조회된 후보 수와 Levenshtein DP cell을 포함한다.

## RED

- 명령:
  `python -m pytest tests/test_fuzzy_matching.py tests/test_config.py tests/test_exceptions.py --no-cov -q`
- 결과: 공개 Fuzzy 예외와 설정·매처가 없어 수집 단계 2개 오류.
- 초기 GREEN 뒤 전체 회귀에서 `새끼손가락` 내부 조각을 삭제형으로 오인한 4개 실패를
  재현했다.
- 정확도 corpus 확장에서 `돌아오는`을 `돌아이`의 치환으로 오인한 추가 실패를 재현했다.

## GREEN

- deletion-signature index와 bounded Levenshtein DP를 구현했다.
- 삭제형만 경계를 강화하는 중간 수정 뒤, 치환형 복합어 오탐까지 제거하기 위해 전체 Fuzzy
  후보를 독립 영숫자 토큰으로 제한했다.
- exhaustive 검증은 `abc`의 모든 3글자 term과 2~4글자 후보 중 기준 Levenshtein distance가
  1인 조합을 공개 Engine 결과와 비교한다.
- Fuzzy·corpus·benchmark 계약: `51 passed`.
- 최종 전체 회귀: `414 passed`, branch coverage `95.59%`.

## 전체 검증

- `uv sync --all-extras --dev --frozen`: 성공
- `uv run ruff format --check .`: 26개 파일 통과
- `uv run ruff check .`: 통과
- `uv run mypy`: 26개 source file, 오류 없음
- `uv run pytest`: `414 passed`, branch coverage `95.59%`
- `uv build`: wheel과 sdist 생성 성공

## 후보 생성 방식 비교

Windows, CPython 3.11.9에서 1,000개 합성 사전과 동일 길이 미탐 probe를 100회씩 7회
측정했다. 두 방식의 결과가 같음을 먼저 확인했다.

| 방식 | 1회당 중앙값 | 상주 index |
| --- | ---: | --- |
| 길이 버킷 전수 Levenshtein | 18.4393ms | 없음 |
| deletion-signature 후보 + Levenshtein | 0.0020ms | signature 2,996개 |

후보가 없는 정상 입력에서 전체 길이 버킷을 반복 비교하는 비용을 피하기 위해 삭제 서명
index를 채택했다. Engine 설정의 index 엔트리 상한으로 custom 사전의 메모리 증가를 제한한다.

## 정확도·성능 기준선

- 12문장, 기대 occurrence 7개: FP 0, FN 0, precision 1.0, recall 1.0.
- Fuzzy 치환 단문: p50 0.0317ms, p95 0.0368ms.
- 1,000개 사전·4,096자 정상 입력: p50 4.6675ms, p95 5.7893ms.
- 같은 Fuzzy 전용 Engine의 retained Python allocation: 4,501,620 bytes.

## 알려진 제한

- 조사·어미가 붙은 오타, 여러 토큰에 걸친 오타, 전치·음운 유사도는 처리하지 않는다.
- 작은 수동 corpus는 실제 서비스의 정상 단어와 오타 분포를 대표하지 않는다.
- 거리 2는 설정할 수 있지만 오탐과 index 크기가 커지므로 기본값은 거리 1이다.
