# Koguard 개발 워크플로

Koguard는 Everything Claude Code(ECC)의 반복 가능한 계획·TDD·검증 패턴을 Python
라이브러리 개발에 맞게 적용한다.

## 1. 작업 분류

- 문서 오탈자나 명백한 단일 수정은 바로 작업하되 관련 검증은 생략하지 않는다.
- 공개 API, 탐지 규칙, 정규화, 사전 로딩, 성능에 영향을 주는 변경은 구현 전에 영향 범위와
  완료 조건을 적는다.
- 외부 패키지, API, 데이터셋처럼 변경 가능성이 있는 대상은 공식 문서와 원본 라이선스를 먼저
  확인한다.

## 2. TDD 루프

### Red

- 새 기능의 기대 동작 또는 버그의 재현 조건을 테스트로 표현한다.
- 실패가 요구사항 때문인지 확인하고, 환경 오류나 잘못된 fixture 때문이면 먼저 바로잡는다.

### Green

- 테스트를 통과시키는 가장 작은 구현을 작성한다.
- 정상 경로와 함께 빈 입력, 최대 길이, Unicode, 다중 매치, Whitelist 겹침을 검토한다.

### Refactor

- 중복을 제거하고 이름과 경계를 정리한다.
- 공개 동작, 매치 순서, 원문 span, 점수 의미가 바뀌지 않았는지 테스트로 확인한다.

## 3. 검증 루프

빠른 피드백부터 전체 검증 순으로 실행한다.

```powershell
# 변경 중
uv run pytest tests/test_target.py
uv run ruff check path/to/changed_file.py

# 완료 전 전체 품질 게이트
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

실패한 명령은 원인을 수정한 뒤 다시 실행한다. 검증을 통과시키기 위해 테스트를 약화하거나
경고를 무시하지 않는다.

## 4. 자체 리뷰

`git diff`를 기준으로 [code-review.md](code-review.md)의 항목을 확인한다. 특히 정상 문장의
오탐, 정규화 후 span, Whitelist가 다른 욕설까지 숨기는 문제, 비결정적 정렬, 최대 입력 길이
우회를 우선 점검한다.

## 5. 전달

완료 보고에는 다음을 포함한다.

- 사용자 관점에서 달라진 동작
- 주요 파일과 설계 결정
- 실행한 검증과 결과
- 실행하지 못한 검증 또는 남은 제한

커밋할 때는 Conventional Commit 타입과 한국어 설명을 사용한다.
