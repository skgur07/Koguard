# 정확도 기준선

측정일: 2026-07-28

대상: Koguard Exact Match + 반복 모음/특수문자 view + 기본 활성화된 공백·혼합·초성·Alias·
Fuzzy 매칭 + 사용자 주입 Whitelist

환경: CPython 3.11.9

## 결과

- 문장 수: 16
- 기대 탐지 occurrence: 17
- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

## 범위

`tests/corpus/exact_cases.json`의 직접 작성한 최소 회귀 corpus를 사용했다. 단일·복수
Exact Match, 반복 매치, 반복 모음 우회, 특수문자 삽입 우회, 정상 문장, 과거 기본
Whitelist 표현의 재분류, 확장된 기본 금칙어를 포함한다. 기본 Whitelist는 비어 있으며
사용자 주입 Whitelist의 구간 보호 동작은 별도 unit test로 검증한다.

이 결과는 구현 회귀를 감지하기 위한 초기 기준선이며 실제 서비스 환경의 정확도를
대표하지 않는다. 외부 데이터셋 검토 이후 corpus 규모와 표현 다양성을 확대하고 수치를
다시 측정한다.

## 초성 매칭 추가 기준선

측정일: 2026-08-04

`tests/corpus/choseong_cases.json`의 직접 작성한 10개 문장과 기대 탐지 occurrence 5개를
기본값과 같은 `EngineConfig(choseong_matching=True)`로 검증했다. 독립 초성 토큰, 쌍자음,
다중 매치,
일반 한글 동일 초성, 앞뒤 자모·숫자 결합, 공백 분리 사례를 포함한다.

- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

이 수치는 작은 수동 회귀 corpus 안에서의 결과다. 실제 채팅 분포의 축약어·이름·도메인
용어가 충분히 포함되지 않았으므로 서비스 정확도를 대표하지 않는다.

## 명시적 Alias 매칭 추가 기준선

측정일: 2026-08-05

`tests/corpus/alias_cases.json`의 직접 선정한 9개 문장과 기대 탐지 occurrence 5개를 기본
`EngineConfig(alias_matching=True)`로 검증했다. `ㅈ같네`, `ㅈ됐네`, 겹받침·복합 자모 Alias와
`3시 발표`, `시 발표`, `수박`, 공백 분리 표현을 포함한다.

- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

이 수치는 다섯 개의 명시적 규칙만 검증한다. 등록하지 않은 신조어와 자모 변형을 일반화하지
않으며 실제 서비스 정확도를 대표하지 않는다.

## MIT Korcen 기본 사전 확장 기준선

측정일: 2026-08-05

MIT 라이선스 Korcen의 고정 revision에서 명시적 표현을 소량 선별한 뒤
`tests/corpus/exact_cases.json`을 20개 문장과 기대 탐지 occurrence 21개로 확장했다.
`GENERAL`, `MINOR`, `PARENT`, `BELITTLE` 계열의 대표 표현과 기존 정상 문장 회귀를 함께
검증한다.

- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

이 수치는 작은 수동 회귀 corpus에만 적용된다. 라이선스가 확인되지 않은 외부 `slang.csv`는
포함하지 않았고, 실제 채팅 분포의 문맥·신조어·표기 변형을 대표하지 않는다.

## 분리 초성·자모·자판 조합 기준선

측정일: 2026-08-06

`tests/corpus/segmented_input_cases.json`의 직접 작성한 9개 문장과 기대 탐지 occurrence 5개를
기본 `EngineConfig(segmented_input_matching=True)`로 검증했다. 공백·구분자로 나뉜 초성,
호환 자모, 영문 두벌식 입력과 `시 발표`, 부분 초성 토큰, 설정되지 않은 구분자, 줄바꿈
오탐 방지 사례를 포함한다.

- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

이 수치는 작은 수동 회귀 corpus에만 적용된다. 정상 영문 문장과 실제 채팅의 초성 표현을 더
확대해 조합 우회로 인한 오탐 예산을 지속해서 검증해야 한다.

## Fuzzy Matching 추가 기준선

측정일: 2026-08-11

`tests/corpus/fuzzy_cases.json`의 직접 작성한 12개 문장과 기대 탐지 occurrence 7개를
`EngineConfig(fuzzy_matching=True)`와 3개 사전어로 검증했다. 한 글자 치환·삭제·삽입,
다중 매치, Exact 우선순위와 함께 `새끼손가락`, `돌아오는`, 토큰 내부 삭제형, 구분자 입력,
정상 문장을 오탐 방지 사례로 포함한다.

- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

이 수치는 독립 영숫자 토큰의 작은 수동 corpus에만 적용된다. 조사·어미가 붙은 오타와 실제
서비스의 정상 단어 분포를 대표하지 않으며, 외부 데이터셋 검토 후 false-positive 예산을 다시
측정해야 한다.

## 독립 평가 corpus 기준선

측정일: 2026-09-04

`evaluation/corpus`의 166개 케이스(hard negative 122, positive 40, review 4)를 기본
`KoguardEngine()`으로 측정했다. 이 corpus는 기존 `tests/corpus/*`와 달리 구현 회귀가 아니라
정상 문장 오탐을 측정하기 위해 작성했다. 재현 명령은 다음과 같다.

```powershell
uv run python -m evaluation.koguard_runner --split all --ablation
```

### 전체 결과

| 지표 | 값 |
| --- | --- |
| occurrence precision | 0.7091 |
| occurrence recall | 0.9286 |
| occurrence F1 | 0.8041 |
| 문장 수준 F1 | 0.8387 |
| 정상 문장 false-positive rate | **11.4754%** (14/122) |
| exact span 일치율 | 1.0000 |
| 판정 보류 제외 | 4건 |

정상 문장 FP rate 11.48%는 계획 §8.3의 balanced 게이트 0.5%를 23배 초과한다. 기존
`tests/corpus/*`가 precision 1.0을 보고해 온 것은 정상 문장 대조군이 사실상 없었기
때문이며, 구현이 좋아서가 아니다.

### 오탐 원인

14건 중 11건이 Exact Match, 3건이 Fuzzy다.

| 사전어 | 오탐 사례 | 원인 |
| --- | --- | --- |
| `꺼져` | `불이 꺼져 있었다` | 정상 동사 활용과 동형 |
| `닥쳐` | `닥쳐올 위기에 대비하자` | 정상 동사 활용과 동형 |
| `등신` | `등신대 포스터를 주문했다` | 정상 명사의 부분 문자열 |
| `뒤져` `뒤질` | `서랍을 뒤져 보니` | 정상 동사 활용과 동형 |
| `미친년` | `미친 듯이 연습했더니` | Fuzzy 1글자 삭제 |
| `돌아이` | `돌아 이쪽으로 와` | Fuzzy 1글자 삭제 |

`꺼져`, `닥쳐`, `등신`, `뒤져`, `뒤질`은 문맥 없이는 판별할 수 없는 다의어인데 무조건
차단어로 등록되어 있다. 사전 확장 이전에 이 항목들의 유지 여부를 먼저 결정해야 한다.

### matcher ablation

각 단계를 하나씩 끄고 측정한 leave-one-out 결과다.

| 제거한 단계 | dTP | dFP |
| --- | ---: | ---: |
| exact_matching | -24 | -11 |
| repeated_matching | -1 | 0 |
| separator_matching | -2 | 0 |
| whitespace_gap_matching | -1 | 0 |
| mixed_gap_matching | -1 | 0 |
| choseong_matching | -2 | 0 |
| alias_matching | -2 | 0 |
| keyboard_matching | -1 | 0 |
| jamo_composition_matching | -1 | 0 |
| segmented_input_matching | -1 | 0 |
| **fuzzy_matching** | **0** | **-3** |

우회 탐지 단계는 모두 오탐 없이 탐지를 늘린다. Fuzzy만 이 corpus에서 추가 탐지가 0이고
오탐 3건을 만든다. 조사가 붙어 독립 토큰이 아닌 실제 오타(`빡대가라라고`)는 놓치고,
독립 토큰인 정상어(`미친`, `돌아`)에서만 발화하기 때문이다.

### 추가 발견

`개새`가 `개새끼`와 별도 항목으로 등록되어 있어, `개새애끼`와 `개새기`가 `개새`로 매칭된다.
탐지 자체는 되지만 canonical term이 실제 표현과 어긋난다.

### 범위

이 수치는 직접 작성한 166개 케이스에만 적용된다. 전 케이스가 단일 판정이며 실서비스
분포에서 수집하지 않았다. 계획 §6.7의 목표 규모(positive 500, negative 2,000)에 도달하기
전까지는 구현 간 상대 비교와 회귀 감지 용도로만 사용한다.
