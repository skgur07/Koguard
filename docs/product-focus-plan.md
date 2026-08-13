# Koguard 제품 집중 계획

- 결정일: 2026-08-12
- 상태: 승인된 실행 계획, 2026-08-13 core 판정 정책 보완
- 대상 버전: 최초 공개 `0.1.0` 이전

## 1. 결정 요약

Koguard는 Phase 4 Adapter, Phase 5 Plugin System, Phase 6 Embedding Plugin 구현을 즉시
보류한다. 최초 공개 전의 최우선 목표를 기능 표면 확장이 아니라 다음 다섯 문제의 해결로
바꾼다.

1. 기본 탐지 데이터가 작아 실전 recall이 충분한지 증명되지 않았다.
2. 실서비스 분포를 반영한 독립 평가 corpus가 없다.
3. 사용자가 상세 matcher 설정을 이해하지 않고 쓸 수 있는 단순 API가 없다.
4. 오탐·비용이 큰 고급 단계까지 기본으로 활성화되어 있다.
5. 핵심 recall을 검증하기 전에 Adapter·Plugin·AI가 로드맵을 선점했다.

Phase 4~6은 삭제하지 않는다. 아래 품질 게이트와 재개 조건을 충족할 때까지 `PAUSED` 상태로
보존한다. CI, 패키징, 라이선스 감사처럼 core 공개 품질에 필요한 기존 Phase 7 항목은 품질
트랙과 병행할 수 있지만, Adapter·Plugin·모델을 전제로 하는 배포 작업은 진행하지 않는다.

이 문서는 계획만 확정한다. 현재 코드의 모든 matcher 기본값은 아직 `True`이며, 프로필 API도
아직 구현되지 않았다. 해당 동작은 이 계획의 Q2 단계에서 테스트와 함께 변경한다.

### 1.1 Core 판정 정책 보완

Koguard의 deterministic core는 **문맥과 무관한 lexical 차단기**로 정의한다. 등록된 욕설이나
승인된 변형이 원문 일부에 존재하면 독립 단어, 정상 복합어, 인용·설명, 사용자명 여부와
관계없이 positive다. 예를 들어 `시발점` 안의 `시발`도 core 차단 대상이다. 문맥을 이유로 core
탐지를 자동 해제하지 않는다.

`hard-negative`는 등록 표현이 실제로 포함됐지만 문맥이 정상인 사례가 아니다. 등록 표현과
닮았으나 동일한 표현·승인 변형은 아닌 문자열, 또는 정책 대상 표현이 전혀 없는 문장만 해당한다.
사용자 주입 Whitelist는 서비스 운영자가 명시적으로 선택하는 override이며 기본 정책의 문맥
추론으로 간주하지 않는다.

AI는 core를 대체하거나 core 탐지를 취소하는 기본 단계가 아니다. 향후 선택 옵션으로 두어
사전에 없는 신조어, 암시적 모욕, 복잡한 우회 표현을 추가 검사한다. AI가 실패하거나 비활성화돼도
core 결과는 유지한다. 이 선택적 AI 후단의 구현은 현재 Phase 4 보류를 해제하지 않으며, core
recall corpus와 단순 API가 준비된 뒤 별도 품질·비용·개인정보 게이트를 거쳐 진행한다.

## 2. 제품 포지셔닝

최초 공개 범위는 다음 문장으로 제한한다.

> Koguard는 런타임 의존성 없이 한국어 욕설의 원문 구간을 결정적으로 반환하고, 정확도와
> 계산량을 재현 가능한 corpus와 benchmark로 설명하는 규칙 기반 Python 라이브러리다.

최초 공개의 핵심 가치는 다음 네 가지다.

- 동일 입력과 설정에 대한 결정적 다중 매치 및 원문 span
- 서비스별 사전과 Whitelist를 포함한 명시적 정책 제어
- 엄격 lexical 정책에서 측정한 precision, recall과 규칙 밖 오탐 예산
- 최대 입력, 메모리와 matcher별 계산량 상한

최초 공개의 핵심 가치가 아닌 항목은 다음과 같다.

- 웹 프레임워크별 편의 wrapper
- 범용 Plugin 생태계
- Embedding 또는 원격 AI 모델
- 영어·일본어·중국어 등 다국어 필터
- 정치·인종·성적 표현 등 정책 카테고리의 무분별한 확대

새 범주는 이름만 추가하지 않는다. 라이선스가 확인된 데이터, 정책 정의, 정상 문장 대조군과
평가 결과가 함께 준비될 때만 지원 범위에 포함한다.

## 3. 현재 기준선과 문제 정의

2026-08-12의 `dev` 기준으로 기본 blacklist는 56개, 명시적 Alias는 5개, 기본 Whitelist는
0개다. 414개 자동화 테스트와 95.59% branch coverage는 구현 회귀 방지에는 유효하지만,
기능별 정확도 corpus가 작고 구현에 맞춰 직접 작성되어 실서비스 품질을 대표하지 않는다.

현재 구조의 문제는 패키지 파일 크기 자체가 아니다. core wheel은 런타임 의존성이 없지만,
기본 호출에서 Exact, 반복, separator, whitespace, mixed, 초성, Alias, 두벌식, 자모, 분리
입력, Fuzzy가 모두 활성화된다. 이 복잡성의 대가가 독립 corpus에서 추가 recall과 허용 가능한
오탐으로 입증되지 않았다.

비교 기준 중 하나로 Korcen을 사용하되, Korcen의 출력이나 사전 목록을 정답으로 간주하지
않는다. 비교 대상은 PyPI에 고정된 버전과 artifact hash로 기록하고 동일 gold corpus에서
측정한다. 경쟁 구현의 탐지 결과는 후보 발굴에만 사용할 수 있으며 사람의 gold annotation을
대체하지 않는다.

## 4. 실행 원칙

1. **데이터보다 matcher를 먼저 늘리지 않는다.** 새 알고리즘은 독립 corpus의 구체적인
   false-negative 묶음을 해결해야 한다.
2. **사전 크기를 성공 지표로 사용하지 않는다.** 중복 변형 수보다 slice별 recall과 정책
   lexicon·승인 변형이 없는 문장의 false-positive를 우선한다.
3. **평가 자료와 튜닝 자료를 분리한다.** 규칙 작성자가 본 사례만으로 최종 수치를 계산하지
   않는다.
4. **라이선스가 기능보다 먼저다.** 출처, revision, 허용 범위가 불명확한 데이터는 wheel,
   공개 저장소와 공개 기준선에 포함하지 않는다.
5. **기본값은 문맥 무관 lexical core다.** 등록 term의 substring 탐지를 기본으로 유지하되,
   고비용 Fuzzy·AI 단계는 독립 corpus에서 추가 recall과 비용이 입증된 선택 옵션으로 둔다.
6. **상세 결과 API는 유지하고 진입 API만 단순화한다.** `CheckResult`와 원문 span을 버리지
   않고 boolean 사용 사례를 짧게 만든다.
7. **모든 성능 수치는 정확도와 함께 본다.** 탐지를 끈 결과를 성능 개선으로 인정하지 않는다.

## 5. Workstream A — 탐지 데이터 확장

### 5.1 목표

기본 사전과 Alias를 실전 표현으로 확대하되, 라이선스·오탐 근거·canonical term을 추적할 수
있는 데이터 파이프라인을 만든다. 단순히 Korcen의 정규식과 예외 목록을 복사하는 작업은
금지한다.

### 5.2 데이터 분류

후보는 최소한 다음 축으로 분류한다. 카테고리를 곧바로 공개 `Match` 필드로 추가하지 않고,
우선 build/evaluation metadata로만 관리한다.

- 표현 계열: 직접 욕설, 모욕·비하, 가족 대상 모욕, 성적 모욕, 위협성 표현
- 표기 형태: canonical, 철자 변형, 축약·초성, 자모, 두벌식, 반복, separator, 공백·혼합,
  유사 문자
- 문맥 형태: 독립 토큰, 조사·어미 결합, 복합어 substring, 인용·설명, 사용자명·게임 용어
- 위험 형태: 높은 오탐 가능성, 정책 민감 범주, 다의어, 지역·세대 한정 신조어

문맥 형태는 탐지를 허용하거나 해제하기 위한 label 기준이 아니라 결과 분석용 slice다. 등록
표현이 있으면 인용·설명·복합어에서도 positive로 annotation한다.

### 5.3 후보 레코드

각 후보는 다음 정보를 가져야 한다.

```text
candidate_id
surface
canonical_term
representation_type
proposed_matcher
source_name
source_url
source_revision
license
redistribution_allowed
positive_examples
hard_negative_examples
review_status
review_notes
```

`redistribution_allowed`가 확인되지 않으면 후보 검토 자료로만 유지하고 패키지 데이터로
승격하지 않는다. 외부 자료에서 아이디어만 얻고 표현을 독립적으로 선별한 경우에도 그 사실과
복사하지 않은 경계를 기록한다.

### 5.4 승격 절차

1. 실제 false-negative, 사용자 제보 또는 라이선스가 확인된 자료에서 후보를 수집한다.
2. Unicode 정규화 뒤 기존 term·Alias와 중복되는지 확인한다.
3. canonical term과 가장 좁은 matcher를 정한다. 명시적 Alias로 해결 가능한 표현에 범용
   Fuzzy나 새 normalizer를 추가하지 않는다.
4. 최소 1개 positive와 2개 hard negative를 작성한다. 등록 표현을 포함한 정상 문맥은 positive로
   두고, hard negative는 철자가 비슷하지만 등록 표현·승인 변형은 아닌 대조군으로 작성한다.
5. tuning corpus에서 matcher별 증분 precision/recall을 측정한다.
6. 라이선스와 NOTICE 기록을 검토한다.
7. 승인된 후보만 packaged data에 반영하고 hidden evaluation set을 다시 실행한다.

### 5.5 산출물

- `data/candidates` 또는 동등한 비배포 후보 manifest
- 재현 가능한 사전 build/validation script
- term·Alias 출처와 변환 규칙을 기록한 NOTICE
- 추가·제외 후보와 이유를 기록한 data change log
- 후보별 positive/hard-negative 테스트

### 5.6 완료 조건

- 모든 packaged term과 Alias가 출처 또는 Koguard 직접 선별 표시를 가진다.
- 중복, canonical 충돌, 잘못된 Unicode와 미확인 라이선스가 build 단계에서 차단된다.
- 사전 변경 PR이 matcher별 증분 TP, FP, FN을 보고한다.
- 기본 데이터 확대가 hidden evaluation에서 합의한 FP 예산을 넘지 않는다.
- 목표 term 개수는 Q1 기준선 이후 정한다. raw count만으로 이 workstream을 완료 처리하지
  않는다.

## 6. Workstream B — 실서비스 평가 corpus

### 6.1 corpus 계층

평가 자료는 용도와 공개 가능 여부를 분리한다.

| 계층 | 용도 | 규칙 |
| --- | --- | --- |
| 공개 회귀 corpus | 저장소의 결정적 기능 회귀 | 직접 작성 또는 재배포 허용 사례만 포함 |
| tuning corpus | 사전·규칙·threshold 조정 | 평가 전에 열람 가능, 최종 수치로 사용 금지 |
| hidden evaluation corpus | 릴리스 품질 판정 | 규칙 작성 중 원문 열람 제한, 고정 version 사용 |
| private service corpus | 실제 분포 drift 확인 | 개인정보 제거, 저장·접근·보존 정책 별도 적용 |

### 6.2 최소 평가 slice

최초 기준선은 한 종류의 욕설 문장만 모으지 않고 다음 slice를 모두 포함한다.

- 직접 canonical 욕설
- 철자·음운 변형
- 초성·Alias·두벌식·자모
- 반복·separator·공백·혼합 우회
- Fuzzy 삽입·삭제·치환
- 조사·어미 결합과 토큰 경계
- 정상 복합어와 사전 substring
- 인용, 뉴스, 교육·설명 문맥
- 사용자명, 게임명, 도메인 용어, 코드, URL
- Unicode 호환 문자, combining mark, format character
- 빈 입력, 최대 입력, 다중 매치, Whitelist 혼합
- matcher별 적대적 성능 입력

정상 복합어, 인용·설명, 사용자명·게임 용어도 등록 욕설 substring이 있으면 core positive다.
해당 slice는 의도된 엄격 차단의 recall을 측정한다. 정책 표현이 없는 유사 문자열만
hard-negative로 둔다.

### 6.3 annotation schema

문장 수준 boolean만 저장하지 않는다.

```json
{
  "schema_version": 1,
  "corpus_id": "stable-corpus-id",
  "cases": [
    {
      "id": "stable-case-id",
      "text": "원문",
      "label": "positive",
      "expected_matches": [
        {
          "start": 0,
          "end": 3,
          "canonical_term": "정책상 canonical"
        }
      ],
      "slices": ["direct", "suffix"],
      "source": {
        "kind": "curated",
        "name": "출처명",
        "reference": null,
        "revision": null,
        "redistribution_allowed": true
      },
      "license": "MIT",
      "split": "tuning",
      "notes": "판정 근거"
    }
  ]
}
```

case의 `label`은 `positive`, `hard-negative`, `review` 중 하나다. 애매한 표현은 억지로
positive/negative에 넣지 않고 `review`로 분리한다. 자동 평가에서는 `review` 사례를 제외하되
개수와 사유를 함께 보고한다. 전체 필드와 접근 경계는
[corpus annotation guide](corpus-annotation-guide.md)를 따른다.

### 6.4 annotation 품질

- 정책 가이드에 욕설, 비하, 인용, 정상 substring의 문맥 무관 차단과 명시적 Whitelist override
  경계를 예제로 정의한다.
- 공개 evaluation 후보는 가능하면 두 번 독립 판정하고 불일치를 합의한다.
- 한 명만 판정한 경우 `single_review`를 기록해 결과 해석에서 구분한다.
- 입력 원문에 개인정보가 있으면 비식별화하며, 변환 때문에 탐지 의미가 달라진 사례는
  폐기한다.
- 모델이나 Korcen/Koguard의 예측을 annotation 화면의 기본값으로 보여 주지 않는다.

### 6.5 비교 harness

동일 corpus에서 다음 대상을 실행한다.

- Koguard `strict`
- Koguard `balanced`
- Koguard `aggressive`
- 현재 공개 전 all-enabled 설정
- Korcen의 고정 버전별 필요한 한국어 profile

비교 도구는 버전, wheel SHA-256, Python 버전, OS, 설정, 실행 시각을 결과에 기록한다. Korcen
출력은 boolean 또는 제공되는 pattern 수준에서만 비교하며 Koguard의 span 평가에는 gold
annotation을 사용한다.

### 6.6 필수 지표

- occurrence precision, recall, F1
- 문장 수준 precision, recall, F1
- 정책 lexicon·승인 변형이 없는 문장의 false-positive rate
- slice별 TP, FP, FN과 전체 건수
- exact span 일치율과 canonical term 일치율
- matcher별 증분 TP, FP, FN
- short-chat 및 최대 입력 p50/p95
- cold start, Engine retained allocation, 가능하면 process RSS
- wheel 크기와 필수 런타임 의존성

전체 점수 하나만으로 릴리스를 판정하지 않는다. 전체 F1이 좋아도 정상 substring, Unicode,
최대 입력 slice에서 회귀하면 실패다.

### 6.7 초기 규모와 확장 규칙

Q1의 첫 비교 가능한 기준선은 최소 다음을 목표로 한다.

- positive 문장 500개 이상
- 정상·hard-negative 문장 2,000개 이상
- 핵심 slice마다 positive 30개 또는 해당 slice의 확보 가능한 전량
- 등록 표현을 포함한 정상 substring·인용·설명·사용자명·게임 용어 positive와, 등록 표현이 없는
  철자 유사 hard-negative를 각각 충분히 확보

이 수치는 공개 품질의 종착점이 아니라 첫 통계적 비교 단위다. 한 출처나 한 표현 계열이 전체
positive의 30%를 넘으면 별도 보고하고 편향을 줄인다.

### 6.8 완료 조건

- tuning과 hidden evaluation이 물리적 파일 또는 접근 정책으로 분리된다.
- 모든 공개 사례의 출처와 재배포 권한이 기록된다.
- 동일 환경에서 Koguard profile과 고정 Korcen 버전의 비교 보고서를 재생성할 수 있다.
- 전체 및 slice별 지표가 생성되고 `n`이 없는 비율만 보고하지 않는다.
- 릴리스 후보의 정상 문장 FP 예산과 최소 recall을 수치로 확정한다.

## 7. Workstream C — 단순 사용자 API

### 7.1 목표 API

상세 결과가 필요한 사용자는 기존 `check()`를 유지하고, 단순 사용자는 다음 정도로 끝나야
한다.

```python
from koguard import KoguardEngine

engine = KoguardEngine(profile="balanced")

engine.contains("검사할 문장")  # bool
engine.check("검사할 문장")     # CheckResult
```

전역 singleton 기반 `koguard.check()`는 사전·설정·동시성 정책을 숨기므로 첫 구현에서는
추가하지 않는다. `contains()`는 `check(text).detected`와 완전히 같은 판정을 반환하는 얇은
편의 API로 제한한다.

### 7.2 프로필 계약

프로필은 matcher의 내부 분리를 숨기는 공개 정책이다. 초기 제안은 다음과 같으며 Q1 ablation
결과로 확정한다.

| matcher | strict | balanced 후보 | aggressive |
| --- | ---: | ---: | ---: |
| Exact | on | on | on |
| Alias | on | on | on |
| Repeated | off | on | on |
| Separator | off | on | on |
| Whitespace | off | on 후보 | on |
| Mixed | off | on 후보 | on |
| Keyboard | off | on 후보 | on |
| Jamo composition | off | on 후보 | on |
| Choseong | off | off | on |
| Segmented input | off | off | on |
| Fuzzy | off | off | on |

`balanced 후보` 항목은 자동 채택이 아니다. Q1에서 해당 matcher의 증분 recall, FP와 p95를
측정한 뒤 기본 포함 여부를 결정한다. `aggressive`도 계산량 상한과 Whitelist를 우회하지
않는다.

### 7.3 설정 우선순위

- `KoguardEngine()`은 최초 공개 전에 확정한 기본 profile을 사용한다.
- `profile`과 직접 `EngineConfig`는 동시에 전달할 수 없도록 해 두 정책 출처의 충돌을 막는다.
- 고급 사용자는 기존 `EngineConfig`의 개별 matcher 플래그를 계속 사용할 수 있다.
- resolved config는 `engine.config`에서 확인 가능해야 한다.
- 프로필별 설정은 테스트에서 모든 필드를 명시해 새 matcher가 실수로 기본 활성화되지 않게
  한다.

### 7.4 공개 표면 정리

첫 공개 전에 다음을 감사한다.

- 실제 런타임 경로가 없는 `MatchMethod` 값
- 구현되지 않은 Adapter·Plugin을 암시하는 문서와 import
- 사용자가 이해하기 어려운 중복 설정
- boolean 판정과 상세 판정의 의미 차이
- masking API가 반드시 core에 필요한지 여부

미구현 미래 API는 호환성 약속이 되기 전에 제거한다. masking은 정확한 span으로 사용자가
쉽게 구현할 수 있으므로 실제 반복 요구가 확인될 때까지 공개 core API의 차단 조건으로 삼지
않는다.

### 7.5 완료 조건

- quickstart가 profile 한 개와 `contains()` 또는 `check()` 한 줄로 설명된다.
- profile과 직접 config의 충돌·결정성·thread safety 테스트가 통과한다.
- 기존 상세 `CheckResult`의 다중 매치와 span 계약이 유지된다.
- profile별 정확도·성능 결과가 문서화된다.
- 공개 API에 구현되지 않은 미래 기능의 흔적이 없다.

## 8. Workstream D — 기본 활성화 정책 재설계

### 8.1 현재 문제

현재 모든 matcher가 기본 `True`다. 이는 기능 발견에는 편하지만, 각 단계의 추가 recall과
추가 FP·latency가 검증되지 않은 상태에서 운영 기본값으로 부적절하다. 특히 초성, segmented,
Fuzzy는 넓은 후보 공간이나 추가 index를 사용하므로 `aggressive` 후보로 취급한다.

### 8.2 matcher ablation

각 matcher를 독립적으로 켜고 다음을 기록한다.

- 이전 profile 대비 새로 찾은 TP
- 이전 profile 대비 새로 만든 FP
- 해결한 FN의 slice와 대표 사례
- short-chat 및 최대 입력 p95 변화
- Engine retained memory 변화
- 다른 matcher와 완전히 중복된 매치 수

추가 TP가 없거나 다른 안전한 Alias로 대체 가능한 matcher는 balanced에서 제외한다. 한정된
표현 몇 개 때문에 범용 matcher가 필요한 경우 먼저 명시적 데이터 규칙을 비교한다.

### 8.3 기본 포함 게이트

Q1 기준선에서 수치를 확정하기 전까지 다음을 임시 판정 기준으로 사용한다.

- balanced 전체 정상 문장 FP rate는 0.5% 이하
- matcher 하나의 추가로 정상 문장 FP rate가 0.25%p 넘게 상승하지 않음
- balanced short-chat p95는 동일 환경에서 1ms 이하
- balanced 최대 입력 p95는 동일 환경에서 15ms 이하
- 모든 적대 입력은 설정된 계산량·입력 길이 상한 안에서 종료
- 새 matcher는 전체 recall뿐 아니라 목표 slice recall을 의미 있게 개선

첫 독립 baseline이 이 기준이 비현실적임을 보이면 수치를 조정할 수 있다. 조정은 결과를 본 뒤
통과시키기 위한 임의 변경이 아니라, corpus 규모·서비스 정책·비용 근거와 함께 결정 기록으로
남긴다.

### 8.4 기본값 전환

1. 현재 all-enabled 동작을 `aggressive`로 이름 붙여 기준선을 보존한다.
2. `strict`와 `balanced` 후보를 구현하고 profile별 corpus 결과를 생성한다.
3. balanced 후보 matcher를 ablation 결과로 확정한다.
4. 최초 공개 전 `KoguardEngine()` 기본을 balanced로 바꾼다.
5. README에 profile별 탐지 범위, 오탐·비용 trade-off와 migration 예제를 기록한다.

Koguard가 아직 공개 `0.1.0` 이전이므로 이 전환은 장기 deprecation 없이 할 수 있다. 다만
현재 `dev` 사용자를 위해 all-enabled와 새 balanced의 동작 차이를 migration 문서에 남긴다.

### 8.5 완료 조건

- 모든 matcher가 strict/balanced/aggressive 중 명확한 위치를 가진다.
- balanced 포함 matcher마다 증분 TP/FP/latency 근거가 있다.
- 기본 config가 실수로 새 고급 matcher를 활성화하지 못하는 회귀 테스트가 있다.
- aggressive가 필요 없는 사용자에게 Fuzzy·초성·segmented index 비용이 발생하지 않는다.

## 9. Workstream E — 로드맵 재정렬

기존 Phase 번호 대신 최초 공개 전 품질 트랙을 다음 순서로 실행한다.

### Q0 — 비교 가능한 기준선과 정책 초안

작업:

- corpus schema와 annotation guide 확정
- Koguard current/all-enabled와 Korcen 고정 버전 runner 작성
- 버전·artifact hash·환경을 기록하는 비교 report schema 작성
- 현재 56 term/5 Alias의 matcher별 ablation 측정

완료 조건:

- 같은 gold corpus에서 양쪽 구현을 실행할 수 있음
- tuning/evaluation 분리가 적용됨
- 현재 default의 slice별 TP/FP/FN과 비용이 기록됨

### Q1 — corpus 및 데이터 품질 확대

작업:

- 최소 초기 규모의 positive·hard-negative 수집과 annotation
- 후보 manifest, 라이선스 검토와 build validation 구현
- false-negative cluster별 사전·Alias 확장
- 등록 표현을 포함한 정상 substring·인용·게임·도메인 문맥의 의도된 차단 회귀와, 등록 표현이
  없는 철자 유사 오탐 회귀 확대

완료 조건:

- Workstream A/B 완료 조건 충족
- 릴리스 FP 예산과 최소 recall 확정
- 사전 확장의 hidden evaluation 개선 확인

### Q2 — API와 기본 profile 단순화

작업:

- `strict`, `balanced`, `aggressive` 구현
- `contains()` 편의 API 구현
- matcher ablation으로 balanced 확정
- 공개 enum·설정·문서 표면 감사

완료 조건:

- Workstream C/D 완료 조건 충족
- 기본 profile의 정확도·성능 예산 통과
- all-enabled에서의 migration 문서 제공

### Q3 — 공개 품질 hardening

작업:

- Unicode format character와 실제 false-positive cluster hardening
- 최악 성능 경로 최적화 또는 aggressive 격리
- corpus·benchmark drift 검증 자동화
- wheel/sdist 설치 smoke test와 CI matrix
- 라이선스, NOTICE, changelog, 보안·기여 가이드

완료 조건:

- hidden evaluation과 모든 품질 게이트 통과
- 깨끗한 환경에서 quickstart 재현
- 공개 한계와 비지원 범위 문서화

### Q4 — `0.1.0` 공개 판정

작업:

- TestPyPI smoke test
- 최종 artifact hash 및 SBOM/의존성 기록
- 고정 evaluation report 공개 가능 범위 결정
- `dev`에서 `main` 승격 여부 승인

완료 조건:

- 릴리스 체크리스트에 미해결 차단 항목이 없음
- 실제 품질 수치가 README의 주장과 일치
- 버전과 공개 API가 확정됨

## 10. Phase 4~6 재개 조건

### Adapter 재개

다음을 모두 충족할 때만 재개한다.

- Q2 완료 및 core API가 안정됨
- Q3 정확도·성능 게이트가 통과됨
- 최소 두 개의 실제 통합에서 같은 boilerplate 문제가 확인되거나 사용자의 구체적 요청이 있음
- core 문서만으로 해결되지 않는 event-loop 또는 framing 문제가 재현됨

FastAPI, WebSocket, raw socket을 한 번에 구현하지 않는다. 가장 반복 수요가 큰 한 adapter부터
별도 extra와 integration test로 추가한다.

### Plugin System 재개

다음을 모두 충족할 때만 재개한다.

- core matcher 공개 계약이 안정됨
- 서로 다른 두 종류 이상의 외부 detector 통합 요구가 실제로 존재함
- 단순 callback 하나로 해결할 수 없는 timeout, ordering, error policy 요구가 확인됨
- Plugin 미설치 사용자의 import/startup 비용 예산이 정의됨

### AI/Embedding 재개

다음을 모두 충족할 때만 재개한다.

- Q1 hidden evaluation에서 규칙·사전 확장이 반복적으로 놓치는 cluster가 수치로 확인됨
- 해당 cluster가 Alias 또는 안전한 규칙으로 해결되지 않음
- 합법적으로 평가·보정 가능한 데이터가 있음
- CPU-only, offline, 모델 부재, 개인정보 처리 정책이 정의됨
- 규칙 대비 추가 recall, FP, p95, 메모리와 배포 크기 예산이 사전에 정해짐

AI가 더 높은 전체 점수를 보인다는 이유만으로 core 기본 경로에 넣지 않는다. 최초 구현이
필요해도 별도 extra와 기본 비활성화를 유지한다.

## 11. 우선순위 backlog

| ID | 작업 | 선행 | 산출물 | 완료 판정 |
| --- | --- | --- | --- | --- |
| PF-001 | corpus schema와 annotation guide | 없음 | schema, guide, validator | 예제와 오류 fixture 통과 |
| PF-002 | 비교 runner와 report schema | PF-001 | Koguard/Korcen runner | 버전·hash 포함 재현 보고서 |
| PF-003 | current matcher ablation | PF-002 | matcher별 TP/FP/FN/비용 | 모든 현재 matcher 결과 존재 |
| PF-004 | tuning/evaluation 분리 | PF-001 | split manifest와 접근 규칙 | 중복·누출 검사 통과 |
| PF-005 | 초기 500/2,000 corpus | PF-004 | annotation corpus | slice·출처·판정 품질 충족 |
| PF-006 | 후보 데이터 manifest | PF-001 | provenance manifest | 미확인 라이선스 build 차단 |
| PF-007 | FN cluster 기반 데이터 확장 | PF-003, PF-005, PF-006 | term/Alias와 회귀 | hidden recall 개선, FP 예산 유지 |
| PF-008 | profile API 계약 테스트 | PF-003 | RED 테스트와 profile 표 | 정책 충돌 조건 확정 |
| PF-009 | strict/balanced/aggressive | PF-008 | 구현과 문서 | profile별 정확도·성능 통과 |
| PF-010 | `contains()` API | PF-008 | 편의 API와 테스트 | `check().detected`와 항상 동일 |
| PF-011 | 공개 API 표면 감사 | PF-009 | 제거·유지 결정 기록 | 미래 미구현 표면 없음 |
| PF-012 | Unicode/FP hardening | PF-005, PF-009 | 회귀와 수정 | slice 예산 통과 |
| PF-013 | CI·패키징·라이선스 hardening | PF-007~012 | release workflow | clean install/build 통과 |
| PF-014 | `0.1.0` 공개 판정 | PF-013 | release report | Q4 완료 조건 충족 |

PF-001~PF-003이 다음 구현 사이클이다. PF-005의 대규모 corpus를 기다리는 동안 PF-006의
provenance 형식과 validator를 병렬로 설계할 수 있지만, 데이터 승격은 annotation 정책이
확정된 뒤에 한다.

## 12. 보고 형식과 의사결정 기록

각 품질 PR은 다음을 보고한다.

- 변경한 corpus/data slice와 출처
- 전체 및 slice별 TP, FP, FN, precision, recall, F1
- matcher별 증분 결과
- short/max/adversarial 성능과 메모리
- 라이선스 및 재배포 검토 결과
- default profile 변화 여부
- 알려진 failure cluster와 다음 우선순위

다음 결정은 반드시 별도 기록을 남긴다.

- balanced에 matcher를 포함하거나 제외한 이유
- 평가 corpus와 FP 예산 변경
- 외부 데이터의 포함·제외와 라이선스 판단
- Phase 4~6 재개
- `dev`에서 `main` 승격과 PyPI 공개

## 13. 이번 계획에서 하지 않는 일

- Korcen의 정규식·false-positive 목록을 일괄 복사하지 않는다.
- corpus 수치를 높이기 위해 테스트 기대값을 현재 구현에 맞추지 않는다.
- 평가 set을 본 뒤 같은 set에 맞춰 사전·threshold를 반복 조정하지 않는다.
- Adapter, Plugin, 모델 코드를 미리 scaffold하지 않는다.
- 지원 근거가 없는 다국어·정책 카테고리를 README에 약속하지 않는다.
- 56개 사전을 임의 목표 개수까지 부풀리는 것으로 완료 처리하지 않는다.
