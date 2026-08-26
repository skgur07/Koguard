# 정확도 기준선

> 2026-08-13 정책 보완: 아래 2026-07-28~08-11 수치는 당시 matcher 단위 구현 회귀를
> 기록한 값이다. 문맥 무관 lexical core 정책에서는 등록 substring과 명시적 공백·초성·두벌식
> 우회를 정상 문맥이라는 이유로 hard-negative 처리하지 않는다. 최신 provisional 제품 판정은
> [matcher ablation 기준선](matcher-ablation-baseline.md)을 사용하며, 최종 정확도는 PF-005
> 독립 판정 완료 후 다시 측정한다.

> 2026-08-14 PF-009에서 첫 독립 확정 92건으로 strict·balanced·aggressive를 다시 매핑했다.
> 최신 공개 집계는
> [`pf009-profile-evaluation.report.json`](../evaluation/results/pf009-profile-evaluation.report.json)을
> 사용한다. 이 결과도 tuning 표본이며 아직 최종 gold나 hidden 평가는 아니다.

> 2026-08-18 한국어 literal 4개와 소문자 로마자 literal 3개를 승격한 뒤 같은 92건을
> 재측정했다. `balanced` 문장 recall은 62.9%, occurrence recall은 40.9%로 상승했고 문장 FP는
> 0/30을 유지했다. 일반 입력의 불필요한 Alias·초성 work를 제거한 뒤 short-chat p95 0.0719ms,
> 최대 입력 p95 13.053ms로 기존 15ms 임시 예산도 통과했다.

> 2026-08-19 `새끼`, `병신새끼`를 승격한 최종 후보 사전으로 같은 92건을 다시 측정했다.
> `balanced`는 문장 TP/FP/FN/TN 45/0/17/30, recall 72.6%이며 occurrence TP/FP/FN
> 59/11/51, recall 53.6%다. strict 대비 문장·occurrence TP가 각각 3건 늘고 FP 증분은 0이다.
> 로컬 short-chat p95는 0.0251ms, 최대 입력 p95는 6.1068ms로 임시 gate를 통과했다. 이는
> 92건 tuning 표본의 최신 스냅샷일 뿐 hidden 또는 실서비스 정확도가 아니다.

> 2026-08-20 balanced composition의 추가 500건을 독립 이중 판정하고 387건을 제3 판정했다.
> 최종 평가 가능 표본은 536건(positive 264, hard-negative 272)이며 review 1,964건은 제외했다.
> `balanced` 문장 TP/FP/FN/TN은 141/1/123/271, recall 53.4%이고 occurrence TP/FP/FN은
> 197/32/283, recall 41.0%다. strict 대비 문장 TP +6, FP +1이어서 현재 FP 증분 0 gate는
> 실패했다. 표본이 커지며 이전 92건 수치가 하향 조정됐고, 여전히 hidden 평가는 아니다.

> 2026-08-25 정책 재감사 3건과 source-balanced 추가 500건을 각각 독립 이중 판정하고,
> 불일치 3건과 293건을 제3 판정했다. 평가 가능 표본은 972건(positive 377,
> hard-negative 595)이며 review 1,528건은 제외했다. `balanced` 문장 TP/FP/FN/TN은
> 241/0/136/595, recall 63.9%이고 occurrence TP/FP/FN은 314/41/320, recall 49.5%다.
> strict 대비 문장 TP +10·FP +0이지만 occurrence TP +12·FP +4여서 전체 FP 증분 0 gate는
> 계속 실패한다. 이는 tuning 결과이며 hidden 또는 실서비스 정확도가 아니다.

> 2026-08-26 hard-negative 중심 buffer의 첫 500건을 독립 이중 판정하고 불일치 452건을 제3
> 판정했다. 새 batch는 positive 12건, hard-negative 471건, review 17건이며 기존 결과와 합친
> 평가 가능 표본은 1,455건(positive 389, hard-negative 1,066)이다. `balanced` 문장
> TP/FP/FN/TN은 243/0/146/1,066, recall 62.5%이고 occurrence TP/FP/FN은 316/41/332,
> recall 48.8%다. strict 대비 문장 TP +10·FP +0, occurrence TP +12·FP +4라는 결론은
> 유지된다. 추가 hard-negative에서 문장 FP가 없었지만 여전히 tuning이며 hidden 평가가 아니다.
>
> 2026-08-26 나머지 hard-negative buffer 500건도 이전 queue와 중복 없이 독립 이중 판정하고
> 불일치 484건을 제3 판정했다. 새 batch는 positive 29건, hard-negative 451건, review 20건이며
> 누적 평가 가능 표본은 1,935건(positive 418, hard-negative 1,517)이다. `balanced` 문장
> TP/FP/FN/TN은 254/2/164/1,515, recall 60.8%이고 occurrence TP/FP/FN은 326/45/355,
> recall 47.9%다. strict 대비 문장 TP +13·FP +0, occurrence TP +13·FP +6이다. 두 profile에
> 공통인 문장 FP 2건과 occurrence gate 실패가 남아 있으며 hidden 평가가 아니다.
>
> 같은 날 공통 FP 2건을 이전 판정 없이 재감사했고 두 reviewer가 모두 문맥 무관 policy
> positive로 합의했다. 수정 후 표본은 positive 420건, hard-negative 1,515건이며 `balanced`
> 문장 TP/FP/FN/TN은 256/0/164/1,515, recall 61.0%다. occurrence TP/FP/FN은
> 328/43/355, recall 48.0%이며 strict 대비 occurrence FP +6 gate와 hidden 검증은 남아 있다.

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
정상 문장을 오탐 방지 사례로 포함한다. 이 fixture는 `개새끼` 등 3개 단어만 주입한 Fuzzy
matcher 단위 기준선이다. 2026-08-19 이후 기본 사전은 별도 정책 결정으로 `새끼` literal을
포함하므로 기본 `balanced`에서는 `새끼손가락`도 Exact Match로 탐지한다.

- False Positive: 0
- False Negative: 0
- Precision: 1.0
- Recall: 1.0

이 수치는 독립 영숫자 토큰의 작은 수동 corpus에만 적용된다. 조사·어미가 붙은 오타와 실제
서비스의 정상 단어 분포를 대표하지 않으며, 외부 데이터셋 검토 후 false-positive 예산을 다시
측정해야 한다.
