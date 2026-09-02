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

Whitespace·Mixed-gap과 Choseong 후보는 기존 전체 영숫자 토큰 경계를 유지하되, 후보 바로 뒤의
남은 한글 토큰이 닫힌 한국어 조사 목록과 정확히 같으면 조사 앞도 유효한 끝 경계로 인정한다.
따라서 `aggressive`는 `시  발은`, `시 * 발은`, `ㅅ ㅂ이`를 탐지하고, Choseong이 켜진
`balanced`는 연속 표기 `ㅅㅂ이`를 탐지한다. `시 발표`, `개 새끼손가락`, 추가 초성·숫자가
붙은 토큰은 계속 제외한다.

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

2026-08-19 최종 후보 사전 재측정에서도 profile 간 결론은 유지됐다. strict는 문장
TP/FP/FN/TN 42/0/20/30, balanced는 45/0/17/30, aggressive는 47/0/15/30이다. occurrence는
각각 TP/FP/FN 56/11/54, 59/11/51, 60/13/50이다. balanced는 strict 대비 문장·occurrence
TP를 각각 3건 늘리고 FP를 늘리지 않아 임시 gate를 통과했다. aggressive는 문장 TP 2건을 더
얻지만 occurrence FP도 2건 늘리므로 기본값으로 승격하지 않는다.

2026-08-20 추가 독립 판정으로 표본을 536건까지 늘리자 strict는 문장 TP/FP/FN/TN
135/0/129/272, balanced는 141/1/123/271, aggressive는 149/2/115/270이었다. balanced는
strict보다 문장 TP 6건을 더 찾지만 FP도 1건 늘어 현재의 FP 증분 0 gate는 실패한다. 이 결과는
`balanced` 공개 계약을 즉시 변경하지 않지만, hidden 평가 전 기본값을 재검토해야 하는 근거로
기록한다.

2026-08-25 정책 재감사와 source-balanced batch-002를 반영해 표본을 972건으로 늘렸다. strict는
문장 TP/FP/FN/TN 231/0/146/595, balanced는 241/0/136/595, aggressive는
250/10/127/585다. balanced는 strict보다 문장 TP 10건을 더 찾고 FP 증분은 0건이지만,
occurrence는 TP +12와 함께 FP +4가 발생한다. 문장 오탐 gate 개선만으로 전체 gate를 통과한
것은 아니며 hidden 평가 전 기본 profile 계약은 유지한다.

2026-08-26 hard-negative buffer의 첫 500건 판정을 더해 표본을 1,455건으로 늘렸다. strict는
문장 TP/FP/FN/TN 233/0/156/1,066, balanced는 243/0/146/1,066, aggressive는
253/15/136/1,051이다. balanced의 strict 대비 문장 TP +10·FP +0, occurrence TP +12·FP +4는
유지됐다. hard-negative 표본 확대에도 문장 FP는 0건이지만 occurrence gate와 hidden 검증이
남아 있어 기본 profile 계약은 바꾸지 않는다.

같은 날 이전 queue를 제외한 나머지 500건 판정을 더해 표본은 1,935건(positive 418,
hard-negative 1,517)으로 늘었다. strict 문장 TP/FP/FN/TN은 241/2/177/1,515, balanced는
254/2/164/1,515다. balanced의 strict 대비 문장 TP +13·FP +0, occurrence TP +13·FP +6으로
문장 FP 증분은 없지만 두 profile 공통 FP 2건과 occurrence gate 실패가 확인됐다.

공통 FP 2건을 이전 판정 없이 재감사한 결과 두 reviewer가 모두 문맥 무관 core positive로
합의했다. 수정 후 strict 문장 TP/FP/FN/TN은 243/0/177/1,515, balanced는
256/0/164/1,515다. balanced 문장 recall은 61.0%이고 occurrence TP/FP/FN은 328/43/355다.
strict 대비 occurrence FP +6이 남으므로 profile 계약과 전체 gate 실패 상태는 유지한다.

2026-08-27 중복 없는 balanced batch-003 500건 판정을 반영해 표본은 2,363건(positive 538,
hard-negative 1,825)으로 늘었다. strict 문장 TP/FP/FN/TN은 334/0/204/1,825, balanced는
351/0/187/1,825다. balanced 문장 recall은 65.2%, occurrence TP/FP/FN은 452/43/380,
recall은 54.3%다. strict 대비 문장 TP +17·FP +0, occurrence TP +18·FP +6이므로 기본 profile
계약과 전체 gate 실패 상태는 유지한다.

2026-08-28 중복 없는 balanced batch-004 500건과 공통 Exact/Alias FP 재감사를 반영해 표본은
2,763건(positive 639, hard-negative 2,124)이다. strict 문장 TP/FP/FN/TN은
416/0/223/2,124, balanced는 440/0/199/2,124이며 balanced recall은 68.9%다. balanced
초성 occurrence FP 후보 7건의 블라인드 재감사 후 occurrence TP/FP/FN은 584/39/390,
recall 60.0%로 strict보다 TP 30건과 FP 2건이 늘었다. 문장 FP 0과 로컬 성능 예산은 통과하지만
occurrence FP 증분 때문에 전체 gate 실패 상태를 유지한다.

2026-09-02 프로젝트 작성 변형 buffer 480건의 독립 이중 판정에서는 positive 240건과
hard-negative 240건에 전부 합의했다. strict·balanced 문장 TP/FP/FN/TN은 둘 다
63/0/177/240이고 aggressive는 240/0/0/240이다. 조사 경계 보강으로 aggressive가 회복한
60건은 Whitespace·Mixed-gap 각 30건이다. 최초 Alias occurrence 12건 불일치는 두 reviewer가
packaged Alias 매핑으로 독립 재감사해 canonical을 교정했고 span·label 오류는 0건이었다.
최종 aggressive occurrence TP/FP/FN은 240/0/0이다. 이 표본은 targeted tuning이며
`gold_ready=false`다.

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
