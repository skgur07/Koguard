# 정확도 기준선

> 2026-08-13 정책 보완: 아래 2026-07-28~08-11 수치는 당시 matcher 단위 구현 회귀를
> 기록한 값이다. 문맥 무관 lexical core 정책에서는 등록 substring과 명시적 공백·초성·두벌식
> 우회를 정상 문맥이라는 이유로 hard-negative 처리하지 않는다. 최신 provisional 제품 판정은
> [matcher ablation 기준선](matcher-ablation-baseline.md)을 사용하며, 최종 정확도는 PF-005
> 독립 판정 완료 후 다시 측정한다.

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
