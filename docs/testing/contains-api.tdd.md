# PF-010 `contains()` TDD 기록

## RED

`tests/test_contains.py`에 profile·직접 설정 동등성, 사용자 사전과 Whitelist, 입력 예외,
길이 제한, 단일 `check()` 위임과 동시 호출 계약을 먼저 추가했다. 구현 전 대상 테스트 12개가
모두 `AttributeError: 'KoguardEngine' object has no attribute 'contains'`로 실패해 새 공개 API의
부재만 재현했다.

## GREEN

`KoguardEngine.contains()`를 `return self.check(text).detected`로 구현했다. 별도 정규화,
matcher, 전역 singleton이나 캐시를 추가하지 않았고 같은 대상 테스트 12개가 통과했다.

## 회귀 의도

- 세 profile과 직접 `EngineConfig`에서 boolean 판정이 상세 판정과 달라지지 않는다.
- 사용자 사전과 겹치는 Whitelist 정책을 우회하지 않는다.
- `TypeError`와 `InputTooLongError`의 종류, 메시지와 길이 정보가 유지된다.
- 공개 반환형은 정확한 `bool`이고 한 호출에서 `check()`를 한 번만 실행한다.
- 같은 engine의 동시 호출 결과가 결정적이다.

## 전체 검증

- `ruff format --check`: 51개 파일 통과
- `ruff check`: 통과
- `mypy`: 51개 source file 통과
- `pytest`: 571개 통과, branch coverage 95.69%
- `uv build`: sdist와 wheel 생성 통과
- sdist에 구현·테스트·공개 계약 문서가 포함되고 wheel에는 runtime package만 포함됨을 확인
