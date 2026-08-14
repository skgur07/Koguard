# Koguard `contains()` 공개 계약

상태: PF-010에서 구현한 `0.1.0` 공개 전 계약.

## 목적

상세 match 정보가 필요 없는 사용자가 탐지 여부를 `bool` 한 값으로 확인하게 한다. 이 API는
새 탐지 정책이나 빠른 조기 종료 경로가 아니라 기존 `check()`의 얇은 편의 메서드다.

```python
from koguard import KoguardEngine

engine = KoguardEngine(profile="balanced")

engine.contains("검사할 문장")  # bool
engine.check("검사할 문장")     # CheckResult
```

## 동작 계약

모든 유효한 engine과 입력에 다음 등식이 성립한다.

```python
engine.contains(text) == engine.check(text).detected
```

- `contains()`는 내부에서 `check()`를 정확히 한 번 호출하고 그 결과의 `detected`를 반환한다.
- profile, 직접 `EngineConfig`, 기본·사용자 사전과 Whitelist 판정을 그대로 사용한다.
- 문자열이 아닌 입력의 `TypeError`와 최대 길이 초과의 `InputTooLongError`를 그대로 전달한다.
- 최대 입력 길이와 Fuzzy 계산량 제한을 포함한 기존 안전 상한을 우회하지 않는다.
- 하나의 불변 engine 인스턴스에서 `check()`와 같은 thread-safety 계약을 가진다.
- 전역 singleton, 숨은 캐시, 추가 의존성이나 모듈 수준 `koguard.contains()`는 만들지 않는다.

## 성능과 사용 선택

`contains()`는 결과가 하나 발견됐을 때 조기 종료하지 않는다. `check()`와 같은 전체 탐지
파이프라인을 실행하고 같은 `CheckResult`를 만든 뒤 `bool`만 반환하므로, 현재 보장하는 이점은
호출 편의성과 단순한 반환 타입이다. 상세 결과도 사용할 코드에서는 두 메서드를 연달아
호출하지 말고 다음처럼 `check()` 결과를 재사용한다.

```python
result = engine.check("검사할 문장")
if result.detected:
    print(result.matches)
```

향후 조기 종료 최적화를 검토하더라도 Whitelist, match 우선순위, 예외와 계산량 상한의 동등성을
독립적으로 증명하기 전에는 이 공개 계약을 변경하지 않는다.
