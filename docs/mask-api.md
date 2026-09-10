# 마스킹 API

`KoguardEngine.mask(text: str, *, char: str = "*") -> str`

- `check(text)`를 한 번 호출하고 최종 매치의 원문 `[start, end)`를 가린다.
- Unicode 코드 포인트당 대체 문자 한 개를 사용한다. 화면 글자 수나 바이트 수 기준이 아니다.
- `char`는 문자열이 아니면 TypeError, 길이가 1이 아니면 ValueError다. char를 먼저 검증한다.
- 겹치는 후보 선택과 Whitelist는 기존 `check()` 정책을 그대로 따른다.
- 우회 표현의 매치 구간 안에 있는 공백·기호·제거 문자도 가린다.
- 매치 밖의 원문은 정규화하지 않는다. 매치가 없으면 원문을 그대로 반환한다.
- 입력 타입·최대 길이·Fuzzy 계산량 예외를 그대로 전달한다. 실패 시 부분 문자열을 반환하지 않는다.
- 기본 balanced와 기존 `contains()`·`check()` 실행 경로는 유지한다.

```python
from koguard import KoguardEngine

engine = KoguardEngine(profile="aggressive")
assert engine.mask("시 * 발 하지 마") == "***** 하지 마"
assert engine.mask("븅신 하지 마", char="#") == "## 하지 마"
```

마스킹은 탐지 결과의 출력 기능이며 미탐지를 보완하지 않는다. 전체 구간을 탐지하므로
조기 반환 최적화 API가 아니며, 호출 시간에는 기존 check 비용과 문자열 치환 비용이 포함된다.
