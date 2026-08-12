# PF-005 초기 corpus 구축 상태

- 기준일: 2026-08-12
- 상태: intake 완료, gold annotation 미완료
- annotation workflow: 구현 완료, 실제 독립 판정 미착수
- 로컬 tuning review: 2,500건
- 확정 positive: 0건
- 확정 hard-negative: 0건
- hidden evaluation: 0건

## 현재 결과

MIT로 재배포 가능한 `2runo/Curse-detection-data`의 고정 commit과 artifact를 검증하고, 전체
5,825건에서 2,500건을 deterministic SHA-256 rank로 선택했다. upstream label별 선택량은
`0: 500`, `1: 2,000`이지만 이 값은 Koguard gold가 아니다. 모든 생성 case는 `review`,
`unadjudicated-intake`, `tuning`으로 저장하며 external label을 case에서 제거했다.

| 항목 | 값 |
| --- | ---: |
| upstream rows | 5,825 |
| selected review rows | 2,500 |
| stable manifest assignments | 2,520 (기존 regression 20 포함) |
| direct/normalized leaks | 0 |
| 자동 민감 패턴 제외 | 25/5,825 |
| 재배포 권한 확인 | 2,500/2,500 |
| Koguard-policy adjudicated | 0/2,500 |
| exact span annotated | 0/2,500 |

## 재현성

- source revision: `ff241621e103b6f220d30de324d0d07987887308`
- source artifact SHA-256:
  `1c3489417e4972dbbbdde19cc47bb8638292891f7f1a443ecbdc2e3c6843545a`
- upstream LICENSE SHA-256:
  `5cb5b18cc855e245f8e299b931a1203479a56fd79a752b102d623056ba5d7c2c`
- generated corpus SHA-256:
  `c26c942a3d825e1667d2d520d41fcda6f03a4e07d81ad4d8ba84038096125b83`
- intake report SHA-256:
  `385832a9b0d264eaa4c3bc248f64eec6287ff0451d7a1a431ae29dab2b1c7af9`
- split manifest v2 SHA-256:
  `ae9b87258ebf02f8ef6078f290360ff1ab1b2ea9f5566842e4d7e319fe4fd502`

```powershell
uv run python -m evaluation.corpus_intake `
  evaluation\sources\curse-detection-data.v1.json `
  C:\artifacts\curse-detection-data-ff241621.txt `
  --output evaluation\corpus\tuning\curse-review-intake-v1.json `
  --report evaluation\results\curse-review-intake-v1.report.json

uv run python -m evaluation.split_manifest_builder `
  evaluation\splits\corpus-splits.v1.json `
  evaluation\corpus\provisional-ablation.json `
  evaluation\corpus\tuning\curse-review-intake-v1.json `
  --manifest-version 2 `
  --change-reason "PF-005 licensed tuning review intake" `
  --output evaluation\splits\corpus-splits.v2.json
```

## 편향과 품질 한계

현재 2,500건은 한 출처가 100%를 차지해 이슈 기준의 30%를 넘는다. 외부 댓글 분포, 정책과
annotation 방식도 단일 출처에 종속된다. 완화하려면 직접 작성한 정상 substring·인용/설명·
사용자명/게임 용어를 각각 100건 이상 추가하고, 재배포 가능한 서로 다른 출처를 두 개 이상 더
확보해야 한다.

`unadjudicated-intake`는 실제 평가 slice가 아니라 판정 대기 상태다. 현재는 direct, 변형, 우회,
정상 substring 같은 slice별 TP·FP·FN을 계산할 수 없다. runner가 `review`를 자동 제외하므로 이
자료로 허위 정확도 수치가 생성되지는 않는다.

선택 전 전체 5,825건에서 이메일·URL·전화번호·주민번호형·IP·6자리 이상 숫자·@handle 후보
25건을 자동 제외했다. 이 검사는 명백한 패턴의 방어선일 뿐 이름이나 간접 식별자를 보장하지
못하므로 사람의 privacy review가 끝나기 전에는 gold로 승격하지 않는다.

수동 privacy review가 끝나지 않은 원문을 공개하지 않고 runtime 크기에 평가 원문 비용도
전가하지 않도록 2,500건 intake는 Git, wheel, sdist에서 모두 제외한다. 로컬 생성 artifact는
보호 경로에서 유지한다. source pin, 생성기, license notice, aggregate report와 stable-ID
manifest는 sdist에 남아 고정 upstream artifact로 corpus를 재생성·검증할 수 있다.

## PF-005 종료 전 남은 작업

1. 100건 단위 primary/secondary batch를 생성하고 실제 독립 판정 시작
2. 탐지기 예측이나 upstream label을 보지 않는 1차 Koguard-policy 판정
3. positive의 exact original span과 canonical term annotation
4. 독립 2차 판정과 불일치 합의, 불확실 사례의 review 유지
5. 핵심 positive slice별 30건, 정상 substring·인용/설명·사용자명/게임 negative 각 100건 확보
6. 단일 출처 100% 편향 완화
7. corpus custodian이 별도 hidden evaluation을 구축하고 PF-004 누출 검사를 실행
8. 확정 positive 500건·hard-negative 2,000건으로 전체 및 slice별 지표 재생성

이 조건 전에는 #7을 완료로 닫거나 2,500건을 실서비스 gold corpus라고 부르지 않는다.
