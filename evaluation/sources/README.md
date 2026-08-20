# External corpus source pins

외부 corpus는 원문을 가져오기 전에 repository, commit, artifact SHA-256, LICENSE SHA-256과
재배포 조건을 source spec으로 고정한다. intake runner는 다운로드하지 않으며 운영자가 별도로
확보한 artifact가 spec과 정확히 일치할 때만 변환한다.

## Curse-detection-data v1

- upstream: <https://github.com/2runo/Curse-detection-data>
- revision: `ff241621e103b6f220d30de324d0d07987887308`
- upstream 설명: 한국어 커뮤니티 댓글 5,825문장의 욕설 여부 분류 자료
- license: MIT, Copyright (c) 2020 2runo
- source spec: `curse-detection-data.v1.json`
- bundled notice: `licenses/curse-detection-data-MIT.txt`

upstream의 0/1 판정은 Koguard의 욕설 정책, exact span, canonical term annotation이 아니다.
따라서 Koguard는 이를 gold label로 복사하지 않고 2,500건의 tuning `review` intake만 생성한다.
source label은 deterministic 층화 선택에만 사용하고 생성 case에는 기록하지 않는다.

## KOTE v1

- upstream: <https://github.com/searle-j/KOTE>
- revision: `cafd2c3f54a6f4b25ac74eaa02a2e76c3ef8c977`
- artifact: `train.tsv`, 40,000 rows
- license: MIT
- source spec: `kote.v1.json`

정서 label은 Koguard lexical 정책과 무관하므로 intake에 복사하지 않는다. 750건을 전체 row에서
stable SHA-256 rank로 선택해 모두 tuning `review`로 유지한다.

## BEEP Korean Hate Speech v1

- upstream: <https://github.com/kocohub/korean-hate-speech>
- revision: `f8d05dce2b22007bb149e5139c0060c68ad8f94b`
- artifact: `labeled/train.tsv`, 7,896 rows
- license: CC-BY-SA-4.0
- source spec: `beep-korean-hate-speech.v1.json`

upstream의 `hate`/`offensive`/`none`은 선택 strata로만 사용한다. 각 250건을 골라 750건 review
intake를 만들며 Koguard label·span으로 복사하지 않는다. 향후 원문 또는 annotation 공개물은
CC-BY-SA attribution과 share-alike 경계를 별도로 유지한다.

## 제외한 후보

- Korean UnSmile dataset: 데이터 라이선스가 CC-BY-NC-ND 4.0이므로 상용 사용과 변형이 필요한
  공개 Koguard corpus에 포함하지 않았다.
- KOLD: 공식 repository root에서 데이터 재배포를 허용하는 명시적 LICENSE를 확인하지 못해
  포함하지 않았다.
- NSMC: 공식 README의 License 절이 비어 있어 공개 artifact로 복사하지 않았다.

외부 리소스 목록이나 aggregator의 라이선스 요약만으로 승격하지 않는다. 항상 원 repository의
LICENSE와 고정 revision을 확인한다.

## Rights-pending candidate: ZIZUN malicious comments

`candidates/zizun-korean-malicious-comments.v1.json`은 공개 corpus 승인 목록이 아니라 로컬 분석용
quarantine source pin이다. 고정 dataset, upstream이 선언한 MIT 파일, 구성 설명 README와 기존
Curse exclusion 원본을 모두 hash 검증한 뒤 500건 `review` queue만 생성한다.

집계 저장소의 MIT 선언과 구성 자료 `kocohub/korean-hate-speech`의 CC-BY-SA-4.0을 행별로
구분할 provenance가 없으므로 `redistribution_allowed=false`다. 선언 LICENSE 사본을
`licenses/zizun-declared-MIT.txt`에 남긴 것은 선언 사실을 재현하기 위한 것이며 권리 승인을
뜻하지 않는다. 분석 수치와 최종 검토 항목은
[외부 평가 자료 사용·권리 감사 대장](../../docs/source-rights-audit.md)에 기록한다.
