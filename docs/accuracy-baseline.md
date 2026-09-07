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

## canonical term 일치율 지표 추가와 공개 표면 정리

측정일: 2026-09-04

### canonical term 일치율

계획 §6.6은 "exact span 일치율과 canonical term 일치율"을 필수 지표로 요구하는데 후자가
구현되어 있지 않았다. 이 때문에 실제 욕설 구간을 잡았지만 라벨이 다른 경우가 정상 문장
오탐과 구분 없이 occurrence FP로 집계되었다.

`evaluation/report.py`에 `term_mismatches`와 `canonical_term_agreement`를 추가했다.

| 지표 | 값 |
| --- | --- |
| canonical term 일치율 | 0.9512 |
| 라벨 불일치 | 2건 |

이제 false positive 4건이 다음으로 분해된다.

- 정상 문장 오탐 2건: `hn-kkeojyeo-03`, `hn-dwijil-01`
- 라벨 불일치 2건: `pos-rep-02`, `pos-fuzzy-01`

### `개새`를 제거하지 않기로 한 결정

라벨 불일치 2건은 `badwords.txt`에 `개새`와 `개새끼`가 함께 있어 짧은 쪽이 Exact Match로
먼저 잡히기 때문이다. `개새`를 제거하면 다음과 같다.

| | 현재 | `개새` 제거 |
| --- | ---: | ---: |
| occurrence FP | 4 | 2 |
| occurrence F1 | 0.9176 | 0.9398 |
| 정상 문장 FP rate | 1.64% | 1.64% |

수치는 좋아지지만 `이 개새야`, `개새 진짜`, `개새애끼 뭐야`가 전부 미탐지로 바뀐다. 지금은
라벨이 `개새`일 뿐 문장은 정확히 차단되고 있으며, 문장 수준 precision 0.9512가 이를 이미
반영한다. 모더레이션 관점에서 올바른 차단을 잃는 대가로 occurrence 지표를 올리는 것은
제품 이익이 아니라고 판단해 제거하지 않았다.

`개새애끼`가 `개새끼`로 축약되지 않는 것은 `repeat_reduction_threshold`가 2이기 때문이다.
같은 모음을 한 번만 늘인 표현은 기본값에서 축약하지 않는다는 문서화된 정책과 일치한다.

### 공개 표면 정리

`MatchMethod.TRIE`와 `MatchMethod.EMBEDDING`을 제거했다. `src/koguard` 어디에서도 생성되지
않는 값이었고, 특히 `EMBEDDING`은 보류 상태인 Phase 6을 공개 enum으로 약속하고 있었다.
계획 §7.4의 "미구현 미래 API는 호환성 약속이 되기 전에 제거한다"에 해당한다.
`tests/test_models.py::test_match_method_exposes_only_reachable_values`가 남은 값 목록을
고정한다.

## 프리셋 도입과 contextual tier 적용

측정일: 2026-09-07

### 변경 내용

- `EngineConfig.strict()`, `.balanced()`, `.aggressive()`를 추가했다. 프리셋은 별도 정책
  계층이 아니라 `EngineConfig` 값이며, `EngineConfig()`는 `balanced()`와 같다.
- `꺼져`와 `뒤질`을 `badwords-contextual.txt`로 분리하고
  `KoguardDictionary.default(include_contextual=True)`로만 로드하게 했다.
- `evaluation/koguard_runner.py`에 `--preset`, `--contextual`을 추가하고, ablation을
  기본값 기준의 양방향 측정으로 바꿨다. 이전 구현은 fuzzy가 기본 비활성이 된 뒤에도
  fuzzy를 끄는 방향으로 측정해 dTP 0, dFP 0을 출력했다. 아무것도 재지 않는 행이었다.

### 기본값 결과

| 지표 | 이전 | 이후 |
| --- | ---: | ---: |
| occurrence precision | 0.9070 | **0.9500** |
| occurrence recall | 0.9286 | 0.9048 |
| occurrence F1 | 0.9176 | **0.9268** |
| 문장 수준 F1 | 0.9630 | **0.9744** |
| 정상 문장 false-positive rate | 1.6393% | **0.0000%** |
| canonical term 일치율 | 0.9512 | 0.9500 |
| exact span 일치율 | 1.0000 | 1.0000 |

정상 문장 오탐이 0건이 되었다. 대가는 재현율 0.0238이며 잃은 케이스는 `pos-direct-07`
(`그만 꺼져 봐`) 하나다. 실제 욕설이므로 이 교환은 숨기지 않고 README와 예산 테스트 주석에
적었다.

### 프리셋별 측정

166개 케이스, 기본 사전, 4096자 한국어 입력 기준이다.

| 프리셋 | precision | recall | F1 | 문장 F1 | 정상 문장 FP | 짧은 p95 | 4096자 p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| strict | 0.9333 | 0.6667 | 0.7778 | 0.8235 | 0.00% | 0.047 ms | 3.68 ms |
| balanced | 0.9500 | 0.9048 | 0.9268 | 0.9744 | 0.00% | 0.119 ms | 6.03 ms |
| aggressive | 0.8837 | 0.9048 | 0.8941 | 0.9383 | 2.46% | 0.193 ms | 21.25 ms |
| aggressive + contextual | 0.8478 | 0.9286 | 0.8864 | 0.9286 | 4.10% | 0.340 ms | 22.48 ms |

설계 문서 §4의 예측값과 일치한다. 두 가지를 기록해 둔다.

- `aggressive`의 4096자 p95 21.25ms는 계획 §8.3의 최대 입력 15ms 예산을 넘는다. 이 예산은
  balanced 기본값에 대한 것이므로 게이트 위반은 아니지만, aggressive를 켜는 서비스는 직접
  측정해야 한다.
- `strict`의 정상 문장 FP는 balanced와 같은 0.00%다. 계획 §7.2가 상정한 "오탐 최소 구성"이
  아니라 지연 구성이다. README에 그렇게 적었다.

### 기본값 변경 근거 기록

계획 §12가 요구하는 기록이다. contextual tier 편입 기준은 "정상 국어 용법이 존재하고 그
용법의 보어 집합이 열려 있어 Whitelist로 열거할 수 없는 표현"이다. `닥쳐`(닥쳐올, 닥쳐온,
닥쳐서)와 `등신`(등신대, 등신불)은 결합형이 닫혀 있어 core에 남겼다. corpus 수치가 아니라
이 기준으로 판정했으며, 기준 없이 다의어 5개를 모두 옮기면 문장 F1이 0.9000으로 떨어진다는
측정이 설계 문서 §2에 있다.

### 예산 갱신

정상 문장 오탐 예산을 3건에서 **0건**으로 좁혔다. 도달 가능한 값이 되었으므로 여유를 남길
이유가 없다. 오탐 1건을 만드는 변경은 계획 §12의 결정 기록을 남기도록 강제한다. opt-in
구성의 비용도 5건으로 고정해 대가가 조용히 커지지 않게 했다.
