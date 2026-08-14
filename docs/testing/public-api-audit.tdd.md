# PF-011 공개 API 표면 감사 TDD 기록

## RED

최상위 export와 Engine·Dictionary 공개 멤버의 폐쇄 목록, `MatchMethod` 값, 미래 확장 심볼·모듈·
의존성 부재, 공개 inventory 문서와 `Match` 원문 span 계약을 먼저 테스트했다.

구현 전 대상 테스트에서는 6건이 실패했다.

- 공개 inventory 문서가 없음
- runtime이 없는 `trie`, `embedding` method가 공개 enum에 남음
- `Match(start=None, end=None)`과 boolean span이 허용됨
- 문자열 method가 `MatchMethod` 대신 허용됨

## 결정

- 실제 runtime method와 깨끗한 scalar 결과에 쓰는 `none`만 유지한다.
- Engine이 항상 원문 위치를 반환하므로 `Match.start/end`를 정수 구간으로 닫는다.
- Adapter·Plugin·AI·async·masking·module-level singleton은 0.1.0 비지원으로 기록한다.
- masking은 기존 span으로 구현 가능하므로 반복된 제품 요구가 확인될 때까지 core에서 제외한다.
- 향후 AI는 이름과 import를 예약하지 않는 선택적 post-core 로드맵으로만 남긴다.

## GREEN

`MatchMethod.TRIE`·`EMBEDDING`을 제거하고 `Match.start/end`를 정수로 닫았다. method와 span의
runtime 검증을 추가하고 Engine의 불필요한 optional 분기를 제거했다. 공개 inventory와 과거
계획 문서를 실제 0.1.0 표면에 맞춘 뒤 대상 모델·Engine·inventory 테스트 154개가 통과했다.

## 전체 검증

- `ruff format --check`: 52개 파일 통과
- `ruff check`: 통과
- `mypy`: 52개 source file 통과
- `pytest`: 580개 통과, branch coverage 95.83%
- `uv build`: sdist와 wheel 생성 통과
- sdist에 inventory·TDD·테스트가 포함되고 wheel에는 문서·테스트·미래 확장 디렉터리가 없음
- wheel metadata에 runtime dependency가 없고 격리 설치에서 폐쇄 enum·정수 span을 재현
