# PF-005 multi-source corpus intake TDD 기록

## RED

기존 `corpus_intake.py`는 MIT, `|` 구분자, 0/1 label, 단일 2runo source에 고정되어 KOTE·BEEP
같은 TSV와 다른 SPDX source를 안전하게 추가할 수 없었다. 중복 원문을 오류로만 처리했고 여러
source의 quota와 30% 상한을 검증하는 공개 계약도 없었다.

먼저 다음 실패 테스트를 추가했다.

- TSV header와 일반 label strata, label 없는 전체 quota 지원
- source 내부 중복을 원문 노출 없이 제외
- KOTE·BEEP revision, artifact·license hash, review-only report 고정
- Koguard 직접 작성 100 positive-target·150 hard-negative-target을 blinded review로 생성
- 다중 source 직접·NFKC 중복 제거, quota와 최대 source 비중 검증
- 첫 batch의 확정 92건을 버리지 않고 balanced corpus에 우선 보존
- finalized가 아닌 review case는 annotation 전까지 label·span·slice를 비워 둠

## GREEN

source spec과 intake report를 v2로 올리고 core runtime 의존성 없이 UTF-8 delimited source,
header, 전체 quota 또는 label strata, MIT·Apache-2.0·CC-BY·CC-BY-SA를 지원했다. KOTE 750건과
BEEP 750건을 고정 artifact에서 생성하고 Koguard 직접 작성 review 250건을 추가했다.

`corpus_composer.py`는 2runo/KOTE/BEEP/Koguard curated를 `750/750/750/250`으로 선택한다.
첫 batch 확정 92건을 보존하고 직접·NFKC+casefold 중복을 제거하며 source 비중 30% 상한을
강제한다. 공개 report에는 원문·case ID·canonical term 없이 집계만 기록한다.

## 현재 판정

- balanced tuning composition: 2,500건
- source share: 30% / 30% / 30% / 10%
- carried finalized: positive 62, hard-negative 30
- pending independent review: 2,408
- hidden evaluation: 0
- `gold_ready=false`

source 편향 intake 조건은 충족했지만 독립 이중 판정, 불일치 합의, 수동 privacy review,
positive 500·hard-negative 2,000, hidden evaluation이 남아 #7은 닫지 않는다.
