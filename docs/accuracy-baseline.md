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

## Fuzzy 비활성과 기본 Whitelist 적용 후

측정일: 2026-09-04

`evaluation/corpus`의 같은 166개 케이스를 기본 `KoguardEngine()`으로 다시 측정했다.

### 변경 내용

- `EngineConfig.fuzzy_matching` 기본값을 `True`에서 `False`로 바꿨다.
- `src/koguard/data/whitelist.txt`에 정상 결합형 12개를 등록했다. 이전에는 비어 있었다.

### 결과

| 지표 | 이전 | 이후 |
| --- | --- | --- |
| occurrence precision | 0.7091 | **0.9070** |
| occurrence recall | 0.9286 | 0.9286 |
| occurrence F1 | 0.8041 | **0.9176** |
| 문장 수준 F1 | 0.8387 | **0.9630** |
| 정상 문장 false-positive rate | 11.4754% | **1.6393%** |
| false positive | 16 | **4** |

recall은 그대로 두고 오탐만 줄였다. Whitelist는 구간 보호이므로 `그만 꺼져`, `닥쳐 아무 말도
하지 마`, `등신도 아니고`는 그대로 탐지한다.

### 남은 false positive 4건

| id | 문장 | 원인 |
| --- | --- | --- |
| `hn-kkeojyeo-03` | 촛불이 바람에 꺼져 어두워졌다 | Whitelist에 없는 후행 용언 |
| `hn-dwijil-01` | 온 집을 뒤질 각오로 찾았다 | 관형형 `뒤질` 뒤에 오는 명사가 열린 집합 |
| `pos-rep-02` | 개새애끼 뭐야 | `개새`가 `개새끼`를 가림 |
| `pos-fuzzy-01` | 개새기라고 욕했다 | `개새`가 `개새끼`를 가림 |

앞의 두 건은 Whitelist 항목을 더 넣어서 풀 문제가 아니다. 종결형과 연결형이 형태가 같아
후행 어절이 용언인지 알아야 구분되며, 그 판단에는 용언 사전이 필요하다.

term별 매칭 모드로도 해결되지 않는다. 그 규칙은 `등신대`처럼 사전어 뒤에 다른 어근이 붙어
한 어절을 이루는 경우를 가려내는데, `꺼져`와 `뒤질`은 사전어가 곧 어절 전체라 형태소만으로
구분할 정보가 없다. 남은 방법은 해당 항목을 기본 사전에서 빼고 필요한 서비스만 켜도록
하는 것뿐이다.

뒤의 두 건은 `badwords.txt`에 `개새`와 `개새끼`가 함께 있어 짧은 쪽이 먼저 매칭되는
문제다. 사전 정리로 해결할 수 있다.

### 기본값 변경 근거 기록

제품 집중 계획 §12는 balanced 프로필에 matcher를 포함하거나 제외한 이유를 별도로 기록하도록
요구한다. Fuzzy 제외 근거는 다음과 같다.

- leave-one-out ablation에서 Fuzzy 제거 시 dTP 0, dFP -3
- 조사·어미가 붙은 실제 오타는 어절 길이가 늘어 편집거리 2 이상이 되므로 놓친다
- 반대로 짧은 정상어(`미친`, `돌아`)가 사전어와 편집거리 1이면 오탐한다
- 한국어가 교착어라 형태소 경계 없이는 개선할 수 없고, 형태소 분석기 도입은 런타임 의존성
  없음 원칙과 충돌한다

계획 §8.4는 all-enabled를 `aggressive`로 보존한 뒤 profile을 도입하고 마지막에 기본값을
바꾸도록 정했다. 이번 변경은 profile 도입보다 먼저 Fuzzy 하나만 옮긴 것이므로 계획보다
앞선 부분 실행이다. profile 작업 시 Fuzzy는 `aggressive`에만 포함한다.
