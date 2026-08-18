# 외부 평가 자료 사용·권리 감사 대장

- 기준일: 2026-08-14
- 원칙: 권리 검토가 끝나지 않은 원문은 로컬 quarantine 분석에만 사용하고 Git, wheel,
  sdist와 공개 corpus에 포함하지 않는다.
- 승인 방식: 저장소 단위 선언만 보지 않고 원출처, 파생 관계, 행 단위 provenance, 재배포와
  변형 허용 여부를 함께 검토한다.

## 현재 사용 내역

| 자료 | 이번 작업에서 사용한 범위 | 공개물 포함 | 권리 상태 |
| --- | --- | --- | --- |
| `Tanat05/korean-profanity-resources` | 후보 자료를 찾기 위한 목록으로만 열람 | 없음 | 각 원출처를 별도 확인해야 함 |
| `ZIZUN/korean-malicious-comments-dataset` | 고정 artifact 분석과 로컬 500건 review queue 생성 | source pin, 집계 report, 선언 LICENSE 사본만 | pending |
| `2runo/Curse-detection-data` | 기존 intake 원본 및 ZIZUN 중복 제외 기준 | 기존 승인 범위 유지 | MIT 확인 |
| `kocohub/korean-hate-speech` | ZIZUN 구성 자료의 원출처·license 확인 | 원문 없음 | CC-BY-SA-4.0 확인 |

PF-013 최종 재확인에서 다음 고정 revision과 공개 artifact 경계를 확정했다.

| 자료 | 재확인 revision | 공개 artifact 판정 |
| --- | --- | --- |
| `Tanat05/korcen` | `eecd9763dbdccce3dc96ddb578ef0b6396058fa9` | 선별 literal과 MIT 고지 포함 승인 |
| `2runo/Curse-detection-data` | `ff241621e103b6f220d30de324d0d07987887308` | 원문 제외, 고정 metadata·license·검토 후보 근거만 유지 |
| `Tanat05/korean-profanity-resources` | `289ed960d10a9e6e3096090fba012ca0796fc641` | discovery reference만, 목록 복사 금지 |
| `ZIZUN/korean-malicious-comments-dataset` | `50b92f50e89bb594db5c9ecafea8d48c1dd5b943` | 원문·annotation 공개 금지, local quarantine만 |
| `kocohub/korean-hate-speech` | `f8d05dce2b22007bb149e5139c0060c68ad8f94b` | CC-BY-SA-4.0 구성 출처 reference만 |

Koguard 소유자는 2026-08-18 코드와 직접 작성한 기본 데이터의 MIT 공개를 승인했다. Git 이력의
`s23019 <s23019@gsm.hs.kr>`도 같은 소유자의 이전 identity임을 확인했으며 `.mailmap`으로
`skgur07 <pigjaoki0970@gmail.com>`에 정규화한다. commit hash를 바꾸는 history rewrite는 하지
않는다.

`Tanat05/korean-profanity-resources` 자체의 단어 목록이나 링크된 제3자 원문은 가져오지 않았다.
따라서 해당 목록은 데이터 출처가 아니라 discovery reference다.

PF-007 독립 검토 후보 중 소유자가 승인한 4개 literal은 2026-08-18 기본 사전에 승격했다.
`2runo/Curse-detection-data` 원문은 공개하지 않고 선별 literal, 고정 revision과 MIT 고지만
배포한다. `src/koguard/data/CURSE-DETECTION-DATA-MIT.txt`가 wheel과 sdist에 포함된다.

2026-08-13 PF-007에서는 `2runo/Curse-detection-data`의 독립 판정 첫 100건에서 확인된 상위
false-negative canonical cluster 7개를 provenance manifest의 `candidate`로 기록했다. source는
기존 고정 revision과 MIT 검증을 그대로 참조한다. 이 후보들은 tuning 평가만 수행했으며
`badwords.txt`, wheel 또는 runtime 데이터에는 아직 포함하지 않았다.

## ZIZUN 고정 근거

- repository: <https://github.com/ZIZUN/korean-malicious-comments-dataset>
- revision: `50b92f50e89bb594db5c9ecafea8d48c1dd5b943`
- `Dataset.csv`: 1,054,286 bytes,
  SHA-256 `8fee1801737cd9d1d3bd38eab7ba6b9ba1d8b91b566f49d980c112dcf778be04`
- `LICENSE`: 1,062 bytes,
  SHA-256 `719828109791321378c5b4b479c927f6e971530b5ce5088ff361b7ccf3e3d38d`
- `README.md`: 1,096 bytes,
  SHA-256 `d9f03e0e1857b310baa133d83c4e18d1d20cd852f8361801861e70af0a5cfc51`
- source spec: `evaluation/sources/candidates/zizun-korean-malicious-comments.v1.json`
- upstream 선언 LICENSE 사본: `evaluation/sources/licenses/zizun-declared-MIT.txt`

README가 밝힌 구성은 Korean hate speech 5,182건, Curse dataset 2,032건, 자체 분류
2,786건이다. 고정 `Dataset.csv`는 총 10,000행이지만 label은 `0:4,983`, `1:4,992`,
누락 25건으로 README의 5,000/5,000 설명을 그대로 재현하지 않는다.

## 분석 결과와 사용 한계

| 검사 | 결과 |
| --- | ---: |
| 전체 행 | 10,000 |
| exact unique | 9,987 |
| normalized unique | 9,975 |
| Curse 원본 direct overlap | 1,402 |
| Curse 원본 normalized overlap | 2,010 |
| 민감 패턴 제외 | 1 |
| 중복 정규화 행 제외 | 12 |
| 로컬 review queue | 500 (`0:250`, `1:250`) |

- 로컬 queue SHA-256:
  `163f147ee530f41e9ad62782f944935149facd3bd827e2bc265b2699d2f446d1`
- 원문 없는 집계 report: `evaluation/results/zizun-quarantine-intake-v1.report.json`
- 집계 report SHA-256:
  `69487adba7517cf6e446f29129452d69d2b2c6cf71ccf507bd98ae2dd3afe4b0`

중복률 때문에 이 자료는 기존 Curse intake와 독립적인 실서비스 평가 corpus가 아니다. upstream
label은 Koguard 정책 label이나 exact span annotation이 아니므로 500건 모두 `review`로 생성했고,
원래 label은 생성 case에 복사하지 않았다. 큐는
`evaluation/quarantine/zizun-review-intake-v1.json`에 로컬로만 존재하며 공개 배포에서 제외된다.

## 권리 승인 전 blocker

1. 집계 저장소는 MIT를 선언하지만, README상 5,182건은 CC-BY-SA-4.0인
   `kocohub/korean-hate-speech`에서 왔다.
2. `Dataset.csv`에 행별 원출처가 없어 어떤 행에 어떤 license와 attribution을 적용해야 하는지
   판별할 수 없다.
3. 자체 분류 2,786건의 원문 수집 근거와 개인정보·플랫폼 약관 준수 여부가 행별로 남아 있지 않다.
4. 공개 재배포뿐 아니라 annotation 결과나 변형 corpus 공개가 share-alike 또는 다른 의무를
   발생시키는지 확인해야 한다.
5. 위 문제가 해결되기 전에는 `redistribution_allowed=false`,
   `independent_source_ready=false`, `gold_ready=false`를 유지한다.

## 최종 권리 검토 체크리스트

- ZIZUN maintainer에게 구성별 행 provenance와 집계물 license 적용 근거를 확인한다.
- Korean hate speech의 attribution·share-alike 의무가 Koguard corpus와 평가 산출물에 미치는 영향을
  확인한다.
- 자체 수집분의 원출처, 수집 동의·약관, 개인정보 처리 근거를 확인한다.
- 공개하려는 대상별로 원문, stable hash/ID, annotation, 집계 통계의 허용 범위를 구분한다.
- 승인 근거 문서와 검토자를 기록한 뒤에만 source spec의 별도 승인 버전을 만든다. 기존
  `pending` spec을 제자리에서 승인 상태로 바꾸지 않는다.
