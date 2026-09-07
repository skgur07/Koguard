# 평가 corpus와 annotation 가이드

이 디렉터리는 배포되지 않는 평가 자산이다. `src/koguard`의 wheel에는 포함되지 않으며,
릴리스 품질을 판정하기 위해서만 존재한다. 구조와 규칙은
[docs/product-focus-plan.md](../docs/product-focus-plan.md) §6을 따른다.

## 구성

| 경로 | 내용 |
| --- | --- |
| `schema.py` | annotation 스키마와 slice 정의 |
| `loader.py` | corpus 로딩, 스키마 검증, split 누출 검사 |
| `report.py` | occurrence·문장 수준 지표, canonical term 일치율, slice별 집계 |
| `koguard_runner.py` | Koguard 실행 어댑터, 기준선 출력, matcher ablation |
| `corpus/tuning/` | 사전·규칙 조정에 사용. 최종 수치로 쓰지 않는다 |
| `corpus/evaluation/` | 릴리스 판정용. 규칙 작성 중 열람을 제한한다 |

## 실행

```powershell
uv run python -m evaluation.koguard_runner --split tuning
uv run python -m evaluation.koguard_runner --split all --ablation
```

`--split evaluation`은 릴리스 판정 시점에만 실행한다. 규칙을 고치면서 반복 실행하면
계획 §4의 "평가 자료와 튜닝 자료를 분리한다" 원칙이 깨진다.

## 판정 기준

### 차단으로 판정하는 경우

- 상대를 향한 직접 욕설, 모욕, 비하
- 가족을 대상으로 한 모욕
- 위 표현의 표기 변형: 초성, 자모, 두벌식, 반복, 구분자 삽입, 공백 분리, 오타

### 복합어 정책

현재 기본 정책은 금칙어를 부분 문자열로 포함한 복합어도 차단한다. `시발점`, `병신년`이
여기 해당하며 `README.md`와 `tests/corpus/exact_cases.json`에 같은 판정이 기록되어 있다.
따라서 이런 문장은 hard negative가 아니라 **positive**로 적는다.

이 정책에 동의하지 않는 서비스는 Whitelist를 주입해 해제한다. corpus는 라이브러리의
기본 정책을 기준으로 판정하며, 서비스별 정책을 반영하지 않는다.

### 차단하지 않는 경우 (hard negative)

어떤 합리적 모더레이션 정책으로도 차단하면 안 되는 문장이다. 금칙어가 부분 문자열로
들어 있어도 의미가 전혀 다르면 여기 속한다.

- 어미·활용 충돌: `보지 못했어`, `자지 않고`, `뒤져 보니`, `닥쳐올`
- 정상 명사: `새끼발가락`, `걸레질`, `등신대`, `틀니`, `십자가`
- 고유명사: `한남동`, `미들섹스`, `신도림역`
- 도메인 용어: 게임 용어, 개발 용어, 코드, URL

### 보류로 판정하는 경우 (`status: "review"`)

인용, 교육, 어원 설명, 창작 맥락처럼 정책이 아직 확정되지 않은 문장이다. 자동 평가에서
제외되지만 개수와 사유는 보고에 남는다. 애매하다는 이유로 억지로 positive나 negative에
넣지 않는다.

## 스키마

```json
{
  "id": "hn-boji-01",
  "text": "그 영화는 아직 보지 못했어",
  "expected_matches": [],
  "slices": ["compound_substring", "hard_negative"],
  "source": "curated",
  "license": "curated",
  "split": "tuning",
  "status": "final",
  "single_review": true,
  "notes": "보다+지 어미"
}
```

- `expected_matches`의 span은 **원문 기준 offset**이다. 우회 표기는 원문에 쓰인 표면형
  전체를 가리키고, `canonical_term`에는 사람이 판단한 정답 표현을 적는다. 예를 들어
  `tlqkf`의 span은 `tlqkf` 전체이고 `canonical_term`은 `시발`이다.
- `hard_negative` slice가 붙은 케이스는 `expected_matches`가 반드시 비어 있어야 한다.
- `single_review`는 한 명만 판정했음을 뜻한다. 두 번 독립 판정한 케이스만 `false`로 바꾼다.

## 기대값 작성 원칙

기대값은 구현 출력이 아니라 사람의 판단으로 적는다. 엔진이 다른 결과를 내면 corpus를
고치는 것이 아니라 결과를 발견으로 기록한다. 계획 §13의 "corpus 수치를 높이기 위해 테스트
기대값을 현재 구현에 맞추지 않는다"가 이 규칙이다.

## split 규칙

`loader.load_all_cases()`가 두 split 사이의 본문 중복을 차단한다. 새 케이스를 추가할 때는
같은 문장을 양쪽에 넣지 않는다. 현재 분할은 저작 순서 기준으로 세 건마다 한 건을
`evaluation`으로 보낸 결정적 분할이다.

## 알려진 한계

- 규모가 작다. 계획 §6.7의 목표는 positive 500개, negative 2,000개 이상이다.
- 전 케이스가 `single_review`다. 두 번 독립 판정이 적용되지 않았다.
- 실서비스 분포에서 수집한 문장이 아니라 직접 작성한 문장이다. 신조어와 실제 채팅의
  표기 다양성을 대표하지 않는다.
- `private service corpus` 계층은 아직 없다.
