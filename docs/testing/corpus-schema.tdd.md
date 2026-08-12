# Corpus schema와 validator TDD 증거

관련 이슈: GitHub `#3` / `PF-001`

## 사용자 여정

- annotation 담당자는 구현 예측과 분리된 원문 span·canonical term·판정 label을 기록한다.
- 검토자는 사례의 slice, 출처, 라이선스, split과 판정 근거를 재현할 수 있다.
- 운영자는 공개 회귀, tuning, hidden evaluation, private 자료의 저장 경계를 구분한다.
- CI와 로컬 도구는 잘못된 span, 중복 ID, 미확인 license와 알 수 없는 enum을 원문 노출 없이
  차단한다.

## RED

- 새 정상/오류 fixture와 `tests/test_corpus_validator.py`를 먼저 추가했다.
- 실행 명령:
  `python -m pytest --no-cov tests/test_corpus_validator.py -q`
- 결과: `evaluation` 모듈이 없어 수집 단계에서 `ModuleNotFoundError` 1개로 실패했다.

## GREEN

- Draft 2020-12 JSON schema와 표준 라이브러리 기반 validator를 `evaluation/`에 추가했다.
- case label과 expected match 개수, 원문 span, 비중첩 정렬, 파일 간 ID 중복을 검증한다.
- schema enum을 validator가 직접 읽어 label, slice, source kind, split의 기준 중복을 줄였다.
- 공개 regression과 private split의 재배포·라이선스 경계를 검증한다.
- CLI 오류는 파일·JSON 위치·정책 위반만 출력하며 원문과 canonical term을 출력하지 않는다.
- 대상 테스트: `19 passed`.

## 검증

- `ruff format --check .`: 29개 파일 통과
- `ruff check .`: 통과
- `mypy`: 29개 source file, 오류 없음
- `pytest`: 434개 테스트 통과, branch coverage 95.59%
- `hatchling build`: wheel과 sdist 생성 성공
- artifact 확인: schema·validator·annotation guide는 sdist에 포함되고 wheel에는 포함되지 않음

현재 worktree PATH에는 `uv` 실행 파일이 없어 `uv sync`와 `uv build`를 직접 실행하지 못했다.
기존 CPython 3.11.9 가상환경의 고정된 검사 도구와 uv cache의 Hatchling 1.31.0을 사용해 같은
포맷·린트·타입·테스트·artifact 빌드 범위를 검증했다.
