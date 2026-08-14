# Koguard 탐지 profile 공개 계약

상태: PF-008에서 고정하고 PF-009에서 구현한 `0.1.0` 공개 전 계약.

## 목적

사용자가 내부 matcher를 하나씩 이해하지 않아도 필요한 탐지 범위와 비용을 선택하게 한다.
profile은 우회 표현 탐지 범위를 조절할 뿐, 등록된 욕설과 승인된 Alias를 문맥에 따라 허용하는
정책이 아니다. 예를 들어 사전에 `시발`이 있으면 모든 profile이 `시발점`의 해당 부분 문자열을
탐지한다. 이 core 결과를 끌 수 있는 기본 정책 수단은 겹치는 구간을 명시한 Whitelist뿐이다.

## 공개 생성자 계약

```python
from koguard import EngineConfig, KoguardEngine

default_engine = KoguardEngine()                 # balanced
strict_engine = KoguardEngine(profile="strict")
balanced_engine = KoguardEngine(profile="balanced")
aggressive_engine = KoguardEngine(profile="aggressive")
custom_engine = KoguardEngine(config=EngineConfig(fuzzy_matching=False))
```

- 허용 profile 이름은 소문자 `strict`, `balanced`, `aggressive` 세 개뿐이다.
- profile을 생략하면 `balanced`로 해석한다.
- `profile`과 직접 만든 `EngineConfig`를 동시에 전달하면 `ConfigurationError`를 발생시킨다.
- 알 수 없는 이름, 다른 대소문자 또는 `None` 이외의 문자열이 아닌 값도
  `ConfigurationError`다. `None`은 profile 생략과 동일하게 취급한다.
- 고급 사용자를 위한 직접 `EngineConfig` 경로는 유지하고 전달한 설정을 그대로 사용한다.
- profile이 해석된 전체 불변 설정은 `engine.config`로 확인할 수 있다.

## profile별 matcher 기대표

아래 표는 폐쇄 목록이다. 앞으로 matcher 설정이 추가되더라도 세 profile 중 어디에 포함할지
명시하고 회귀 테스트를 갱신하기 전에는 자동으로 활성화되지 않는다.

| matcher | strict | balanced | aggressive |
| --- | ---: | ---: | ---: |
| Exact | on | on | on |
| Alias | on | on | on |
| Repeated | off | off | on |
| Separator | off | off | on |
| Whitespace gap | off | off | on |
| Mixed gap | off | off | on |
| Keyboard | off | off | on |
| Jamo composition | off | off | on |
| Choseong | off | on | on |
| Segmented input | off | off | on |
| Fuzzy | off | off | on |

입력 길이, Unicode 정규화, 구분자 집합, Fuzzy 계산량 상한 같은 공통 안전 설정은 profile 간에
동일한 `EngineConfig` 기본값을 사용한다.

## balanced 선택 근거

PF-005의 첫 독립 이중 판정 batch에서 확정된 92건을 평가했을 때 Exact+Alias는 문장 기준
TP 33, FP 0, FN 29, TN 30이었다. 모든 matcher를 켠 설정은 TP 37, FP 0, FN 25, TN 30으로
문장 TP가 4건 늘었지만 short-chat p95 약 4배, 최대 입력 p95 약 1.9배, retained memory 약
2.8배의 비용을 사용했다.

matcher 독립 증분 중 Choseong만 TP 3건을 추가하고 FP를 추가하지 않았다. 다른 고급 matcher는
이 batch에서 증분 TP가 없었고, Fuzzy는 occurrence TP 없이 FP 2건을 추가했다. 따라서 첫
`balanced`는 Exact+Alias+Choseong으로 제한한다. 표본이 아직 작고 `gold_ready`가 아니므로 이
선택은 공개 전 추가 corpus 결과로 재검토할 수 있지만, 결과를 바꿀 때는 같은 ablation과
변경 근거를 남긴다.

## 동작 불변 조건

- 모든 profile은 등록된 욕설의 문맥 무관 부분 문자열 Exact 탐지를 보존한다.
- 모든 profile은 검토·승인된 기본 Alias 탐지를 보존한다.
- Whitelist는 겹치는 core match 구간만 보호하며 같은 문장의 다른 match를 제거하지 않는다.
- 동일한 입력, 사전, profile에는 match 내용과 순서가 결정적이다.
- 하나의 engine 인스턴스를 여러 thread의 동시 `check()`·`contains()` 호출에서 안전하게
  공유할 수 있다.
- `contains(text)`는 모든 profile에서 정확히 `check(text).detected`와 같은 판정과 예외를
  사용한다.
- profile은 최대 입력 길이와 matcher 계산량 상한을 우회하지 않는다.
- 향후 AI 검사는 별도 선택적 후처리 계층이며 profile의 core 결과를 취소하지 않는다.

## 기존 all-enabled 사용자의 이동

profile 도입 전 `KoguardEngine()`과 `EngineConfig()`는 모든 matcher를 켰다. PF-009 이후
인자 없는 `KoguardEngine()`은 `balanced`로 바뀐다. 기존 동작이 필요한 사용자는 다음처럼
의도를 명시한다.

```python
engine = KoguardEngine(profile="aggressive")
```

직접 설정을 조립한 기존 코드는 계속 동작한다. 특히
`KoguardEngine(config=EngineConfig())`는 all-enabled 설정을 명시적으로 유지한다.

## 구현 및 평가 결과

PF-009에서 RED 표시를 제거한 공개 계약 테스트를 모두 통과시켰다. 보호된 ablation의 원문,
case ID, canonical 표현을 제외하고 세 profile의 설정·정확도·성능 집계만
[`pf009-profile-evaluation.report.json`](../evaluation/results/pf009-profile-evaluation.report.json)에
공개한다. 공개 전 profile 구성이 바뀌면 독립 평가 근거, 이 문서, 전체 기대표와 테스트를 한
변경으로 함께 갱신한다.
