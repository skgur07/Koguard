# Koguard corpus annotation guide

이 문서는 Koguard의 공개 회귀, tuning, hidden evaluation, private service corpus를 같은 형식으로
판정하기 위한 정책이다. 구현 결과를 정답으로 복사하지 않고 사람이 원문과 정책을 기준으로
annotation한다. 기계 검증 계약은 [`evaluation/corpus.schema.json`](../evaluation/corpus.schema.json),
검증 도구는 [`evaluation/corpus_validator.py`](../evaluation/corpus_validator.py)에 있다.

## 1. 파일 구조

한 JSON 문서는 `schema_version`, `corpus_id`, `cases`를 가진다. `schema_version`은 현재 `1`이며,
`corpus_id`와 case `id`는 소문자 ASCII, 숫자, `.`, `_`, `-`만 사용한다. ID는 파일 이동이나
문장 수정 후에도 결과 이력을 연결할 수 있도록 안정적으로 유지하고, 여러 파일 전체에서
중복되지 않게 한다. ID에는 원문 일부, 사용자명, 계정이나 서비스 내부 식별자를 넣지 않는다.

각 case는 다음 필드를 모두 가진다.

| 필드 | 의미 |
| --- | --- |
| `id` | corpus 전체에서 유일한 안정 ID |
| `text` | 원문. 빈 입력 사례는 빈 문자열 허용 |
| `label` | `positive`, `hard-negative`, `review` 중 하나 |
| `expected_matches` | 원문 span과 canonical term 목록 |
| `slices` | 사례가 검증하는 고정 평가 slice 목록 |
| `source` | 수집 방식, 출처명, reference/revision, 재배포 가능 여부 |
| `license` | SPDX 식별자 또는 검토된 `LicenseRef-*` 값 |
| `split` | `regression`, `tuning`, `evaluation`, `private` 중 하나 |
| `notes` | 판정 근거와 비식별화·불일치 합의 메모 |

정상 예제와 오류 예제는 `tests/fixtures/corpus_validation`에서 확인할 수 있다.

## 2. label 판정

### positive

정책상 차단할 표현이 하나 이상 있는 사례다. `expected_matches`를 최소 하나 작성한다. 탐지기가
현재 찾지 못하더라도 사람이 정한 정답을 유지하며, 구현 결과에 맞춰 canonical term이나 span을
바꾸지 않는다.

### hard-negative

표면상 욕설과 비슷하지만 차단하지 않을 정상 문장이다. 정상 복합어, 인용·교육 문맥, 사용자명,
게임·도메인 용어와 경계 사례가 여기에 해당할 수 있다. `expected_matches`는 반드시 비어 있어야
한다.

### review

정책 또는 문맥만으로 합의하지 못한 사례다. 자동 precision·recall 계산에서 제외하고, 독립
판정자가 합의한 뒤에만 `positive` 또는 `hard-negative`로 바꾼다. review 개수와 사유는 품질
보고서에 남긴다. 탐지기나 비교 대상의 예측을 review 기본값으로 사용하지 않는다.

## 3. span과 canonical term

- span은 UTF-8 byte가 아니라 Python 문자열의 원문 code point index를 사용한 반열림 구간
  `[start, end)`다.
- `0 <= start < end <= len(text)`를 만족해야 한다.
- 목록은 `start` 오름차순으로 쓰고 서로 겹치지 않게 한다.
- `text[start:end]`는 원문 표면형이며 `canonical_term`은 정책상 대표 표현이다. 우회 표기에서는
  둘이 같지 않을 수 있다.
- 정규화한 문자열, 삭제한 구분자 또는 모델이 복원한 위치를 span으로 기록하지 않는다.
- 여러 occurrence는 각각 기록한다. 더 긴 정책 표현이 짧은 표현을 포함하면 실제 Koguard의
  현재 결과가 아니라 annotation 정책에서 선택한 하나의 비중첩 span을 기록한다.

## 4. slice

허용 slice는 JSON schema의 enum이 단일 기준이다. 새 slice가 필요하면 이름만 case에 쓰지 말고
정의, positive·hard-negative 예시와 보고 단위를 검토한 뒤 schema version 또는 enum을 변경한다.
한 사례가 여러 위험을 검증하면 중복 없는 여러 slice를 기록할 수 있다.

핵심 분류는 직접 표현, 철자·음운 변형, Alias·초성·자모·두벌식, 반복·구분자·공백·혼합,
Fuzzy, 조사·경계, 정상 substring, 인용·교육, 사용자명·게임·도메인, Unicode, Whitelist,
최대 입력과 적대 성능 입력이다.

## 5. source와 license

`source.kind`는 다음 중 하나다.

- `curated`: Koguard가 직접 작성·판정한 사례
- `licensed`: 외부 자료에서 허용 범위 안에 포함한 사례
- `private`: 공개할 수 없는 실제 서비스 사례

licensed source는 재현 가능한 `reference`와 `revision`을 반드시 기록한다. 공개 회귀 corpus는
`redistribution_allowed=true`인 사례만 허용한다. URL 접근 가능 여부와 재배포 허용은 다른
문제이므로 이용 가능하다는 이유만으로 `true`를 쓰지 않는다.

private 사례는 `source.kind=private`, `redistribution_allowed=false`,
`license=LicenseRef-Private`를 사용한다. 개인정보를 제거하되 변환으로 탐지 의미가 바뀌면 사례를
폐기한다. validator와 보고서는 오류 위치와 집계만 출력하고 원문을 출력하지 않는다.

## 6. split과 접근 경계

| split | 용도 | 저장·접근 정책 |
| --- | --- | --- |
| `regression` | 공개 저장소의 결정적 기능 회귀 | 재배포 가능한 직접 작성·라이선스 사례만 Git에 저장 |
| `tuning` | 사전·규칙·threshold 조정 | 규칙 작성자가 열람 가능, 최종 품질 수치로 사용 금지 |
| `evaluation` | 릴리스 품질 판정 | 공개 저장소 밖의 제한된 저장소에 고정 version으로 보관 |
| `private` | 실제 서비스 분포·drift 확인 | 비식별화, 최소 접근, 별도 보존·삭제 정책 적용 |

hidden evaluation과 private 원문은 이 공개 저장소, PR 첨부, CI 로그와 issue 본문에 올리지 않는다.
`evaluation/split_guard.py`는 stable-ID manifest 일치, 공개 자료와 hidden evaluation 사이의
동일 원문 및 고정 정규화 변형 중복, protected 원문의 저장소 내부 배치를 차단한다. 운영 역할,
승인과 보존 절차는 [corpus split 정책](corpus-split-policy.md)을 따른다.

## 7. annotation 절차

1. 출처와 재배포 가능 여부를 먼저 기록한다.
2. 원문을 읽고 탐지기 예측 없이 `label`을 판정한다.
3. positive이면 원문 span과 canonical term을 기록한다.
4. 최소 하나의 slice와 판정 근거 notes를 기록한다.
5. 공개 또는 최종 evaluation 후보는 가능하면 두 명이 독립 판정한다.
6. 불일치는 `review`로 분리하고 합의 과정과 결과를 notes에 남긴다.
7. validator를 통과한 뒤에만 corpus version에 포함한다.

## 8. 검증 명령

파일 또는 디렉터리를 한 번에 검증할 수 있다.

```powershell
uv run python -m evaluation.corpus_validator path/to/corpus.json
uv run python -m evaluation.corpus_validator path/to/corpus-directory
uv run python -m evaluation.split_guard path/to/manifest.json path/to/corpus-directory `
  --repository-root .
```

여러 경로를 함께 전달하면 파일을 가로지르는 중복 case ID도 검사한다. 성공 시 파일·case·split·
review 개수만 출력한다. 실패 시 파일과 JSON 위치, 정책 위반만 출력하며 원문이나 canonical
term은 출력하지 않는다.

split guard는 manifest version, split별 건수와 누출 건수만 출력한다. hidden evaluation을
포함한 완전 검증은 corpus custodian이 보호 환경에서 실행하고 aggregate 결과만 전달한다.
