# Koguard 0.1.0 공개 API inventory

상태: PF-011에서 감사한 최초 공개 전 폐쇄 계약.

## 최상위 import 표면

`koguard`가 `__all__`로 내보내는 심볼은 아래 16개뿐이다. 새 공개 심볼은 실제 runtime 경로,
문서와 회귀 테스트를 같은 변경에서 추가하기 전에는 이 목록에 들어오지 않는다.

| 분류 | 공개 심볼 | 실제 사용 경로 |
| --- | --- | --- |
| Engine | `KoguardEngine` | 불변 설정·사전을 조립하고 `contains()`·`check()` 실행 |
| Dictionary | `KoguardDictionary` | 기본 또는 사용자 blacklist·whitelist·Alias 구성 |
| 설정 | `EngineConfig` | 고급 사용자의 matcher·입력·계산량 상한 직접 설정 |
| 타입 | `NormalizationForm` | 사전과 Engine의 `NFC`·`NFKC` 정규화 선택 |
| 타입 | `ProfileName` | `strict`·`balanced`·`aggressive` 폐쇄 profile 이름 |
| 결과 | `CheckResult` | 정규화 문자열, 전체 match, 지연과 scalar 편의 property |
| 결과 | `Match` | canonical term, 원문 구간, method와 score |
| 결과 | `MatchMethod` | 실제 matcher와 깨끗한 scalar 결과의 method 구분 |
| Alias | `AliasMode` | `exact_token`·`token_prefix` 경계 정책 |
| Alias | `AliasRule` | Alias와 canonical blacklist term의 불변 매핑 |
| 예외 | `KoguardError` | Koguard 전용 예외의 공통 base |
| 예외 | `ConfigurationError` | 잘못된 profile·설정·사전/설정 조합 |
| 예외 | `DictionaryError` | 사전 파일·항목·Alias 검증 실패 |
| 예외 | `InputTooLongError` | `max_input_length` 초과 입력 거부 |
| 예외 | `FuzzyOperationLimitError` | Fuzzy 결정적 작업량 상한 초과 |
| 메타데이터 | `__version__` | 설치된 배포 버전 |

`KoguardEngine`의 공개 동작은 `config`, `dictionary`, `contains(text)`, `check(text)`다.
`KoguardDictionary`의 공개 생성 경로는 `default()`와 `from_sources()`이며, 불변 원본 필드와
`ordered_blacklist`, `ordered_whitelist`, `ordered_aliases`를 읽을 수 있다.

## 결과 모델 결정

`MatchMethod`는 다음 값만 제공한다.

- 실제 runtime matcher: `exact`, `repeated`, `separator`, `whitespace`, `mixed`, `choseong`,
  `alias`, `keyboard`, `jamo`, `levenshtein`
- 깨끗한 `CheckResult.method` scalar property: `none`

Engine이 반환하는 모든 `Match`는 원문의 정확한 반열림 구간 `[start, end)`을 가진다.
`start`와 `end`는 `bool`이 아닌 정수이며 `0 <= start < end`다. 원문 구간을 만들 수 없는 미래
detector를 위해 `None`을 미리 허용하지 않는다.

`CheckResult.detected`, `matched_word`, `method`, `confidence`는 모두 현재 구현된 읽기 전용
property이므로 유지한다. 새 코드는 다중 결과와 원문 위치가 보존되는 `matches`를 우선 사용하고,
scalar property는 첫 match의 편의 view로 이해해야 한다.

## 설정 감사

`EngineConfig`의 각 필드는 현재 runtime 분기에 연결된다. 입력·Unicode 상한, matcher별 활성화,
반복·공백·구분자 정책, Fuzzy 후보·작업량 상한은 의미가 서로 달라 병합하거나 제거하지 않는다.
일반 사용자가 이를 모두 이해할 필요는 없으므로 기본 경로는 `balanced` profile로 유지하고 직접
config는 고급 경로로 구분한다.

## 0.1.0에서 제거한 표면

- `MatchMethod.TRIE`: 독립 결과 method를 만드는 runtime이 없고 Exact 구현 세부사항을 공개
  호환성으로 고정하므로 제거했다. 기존 Exact 결과는 계속 `MatchMethod.EXACT`다.
- `MatchMethod.EMBEDDING`: AI·Embedding runtime이 없어 제거했다. 현재 결과를 다른 값으로
  migration할 필요는 없다.
- `Match.start/end=None`: 현재 Engine이 항상 원문 구간을 생성하므로 제거했다. `Match`를 직접
  만들던 코드는 유효한 원문 정수 구간을 제공해야 한다.

위 항목은 PyPI 최초 공개 전 제거하므로 공개 릴리스 간 deprecation 기간은 두지 않는다.

## 비지원 기능과 확장 경계

0.1.0 core에는 Adapter, Plugin manager, AI/Embedding detector, async 검사, masking 함수,
module-level singleton `check()`·`contains()`가 없다. 이를 암시하는 import, 설정, extra와 런타임
의존성도 제공하지 않는다.

masking은 정확한 원문 span으로 호출자가 정책에 맞게 구현할 수 있고, 대체 문자·중첩·보존
규칙에 대한 반복 요구가 아직 없으므로 core에 추가하지 않는다.

```python
result = engine.check(text)
masked = list(text)
for match in result.matches:
    masked[match.start : match.end] = "*" * (match.end - match.start)
masked_text = "".join(masked)
```

향후 AI는 독립 hidden evaluation에서 규칙·사전으로 해결되지 않는 cluster와 비용 예산이 먼저
확인될 때만 선택적 post-core 계층으로 검토한다. 그 계층은 core match를 취소하거나
Whitelist·입력·계산량 상한을 우회할 수 없다. 현재는 구체적인 클래스명, import 경로, method,
버전 또는 의존성을 공개 계약으로 예약하지 않는다.
