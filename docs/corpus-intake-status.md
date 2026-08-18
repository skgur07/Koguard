# PF-005 초기 corpus 구축 상태

- 기준일: 2026-08-12
- 상태: intake 완료, 첫 100건 독립 판정·제3 판정 완료, 전체 corpus 미완료
- annotation workflow: 이중 판정·불일치 제3 판정 구현 및 실제 batch 검증 완료
- 로컬 tuning review: 2,500건
- 확정 positive: 62건
- 확정 hard-negative: 30건
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
| Koguard-policy finalized | 92/2,500 |
| exact span annotated positive | 62건, 110 occurrence |

## 재현성

- source revision: `ff241621e103b6f220d30de324d0d07987887308`
- source artifact SHA-256:
  `1c3489417e4972dbbbdde19cc47bb8638292891f7f1a443ecbdc2e3c6843545a`
- upstream LICENSE SHA-256:
  `5cb5b18cc855e245f8e299b931a1203479a56fd79a752b102d623056ba5d7c2c`
- generated corpus SHA-256:
  `c26c942a3d825e1667d2d520d41fcda6f03a4e07d81ad4d8ba84038096125b83`
- intake report canonical-LF SHA-256:
  `1d2e31ada27896cbd155e4e9ff7779e795ce53b931bc112a69cef4317e0d400a`
- split manifest v2 canonical-LF SHA-256:
  `06dc923ece416dee03cf6db984b319daa6290b7a1b3e212f2f8c0cbb042f846d`

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
annotation 방식도 단일 출처에 종속된다. 완화하려면 등록 표현을 포함한 정상 substring·
인용/설명·사용자명/게임 문맥 positive와 등록 표현이 없는 유사 hard-negative를 직접 작성해
각각 100건 이상 추가하고, 재배포 가능한 서로 다른 출처를 두 개 이상 더 확보해야 한다.

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

## 추가 후보: ZIZUN quarantine

`ZIZUN/korean-malicious-comments-dataset` 10,000행을 별도 후보로 고정했다. 이 중 500건을 로컬
review queue로 만들었지만 기존 Curse 원본과 normalized 기준 2,010건이 겹치므로 PF-005가
요구하는 독립 출처 확충으로 계산하지 않는다. 25건의 label 누락과 구성 자료별 행 provenance
부재도 확인했다.

집계 저장소는 MIT를 선언하지만 구성 설명상 5,182건은 CC-BY-SA-4.0 자료에서 파생됐다.
권리 호환성과 행별 의무를 확인하기 전까지 queue는 Git·배포물에서 제외하고, 모든 case를
`review`와 `redistribution_allowed=false`로 유지한다. 따라서 현재 gold 수량과 hidden evaluation
수량은 증가하지 않았다. 자세한 고정 hash, 사용 내역과 최종 검토 체크리스트는
[외부 평가 자료 사용·권리 감사 대장](source-rights-audit.md)을 따른다.

## 2026-08-13 Codex primary 100건 초안

제품 정책을 문맥 무관 lexical core로 확정하고 첫 100건을 `codex-primary`가 원문만 보고
1차 판정했다. Koguard 예측은 annotation 기본값으로 사용하지 않았으며 판정 후에만 집계 비교했다.

| 항목 | 1차 초안 |
| --- | ---: |
| privacy 검토 완료 | 100 |
| positive | 64 |
| hard-negative | 30 |
| AI 후단·정책 2차 검토 | 6 |
| annotated occurrence | 115 |
| 현재 core가 찾은 positive 문장 | 37/64 |
| 현재 core가 놓친 positive 문장 | 27/64 |
| hard-negative 오탐 | 0/30 |

`37/64`는 단일 AI 판정 초안에 대한 진단값일 뿐 공개 recall이나 gold 기준선이 아니다. 같은
판정자가 secondary를 채우지 않았고, 기존 secondary 100건은 계속 blinded `pending`이다. 따라서
확정 positive·hard-negative 수와 `gold_ready=false`는 바뀌지 않는다. 2차 독립 판정과 불일치
합의가 끝난 뒤에만 이 수치를 기준선으로 다시 계산한다.

## 2026-08-13 첫 100건 독립 판정 결과

서로 결과를 보지 않은 두 검토자가 100건을 모두 판정했고, 최초 불일치 70건은 별도의 세 번째
검토자가 탐지기 결과를 보지 않고 판정했다. 68건은 확정됐고 의미·정책 판단이 더 필요한 2건은
강제로 확정하지 않았다. 최초 합의 30건 중 `review` 6건을 포함해 최종 batch는 positive 62건,
hard-negative 30건, review 8건이다. 개인정보 제외·대기 사례는 없다.

현재 all-enabled를 확정 92건에 적용한 결과는 문장 기준 TP 37, FP 0, FN 25, TN 30으로
precision 100%, recall 59.7%, F1 74.7%다. occurrence 기준은 TP 41, FP 13, FN 69으로
precision 75.9%, recall 37.3%, F1 50.0%다. occurrence FP는 hard-negative 문장 오탐이 아니라
positive 문장 안에서 정답 span·canonical과 일치하지 않은 추가 탐지다.

FN 진단상 110개 정답 occurrence 중 51개가 현재 packaged 사전에 canonical을 갖지 않으며,
29개의 고유 missing canonical cluster로 묶인다. 문장 FN 25건 중 21건은 정답 canonical이 모두
사전에 없고, 1건은 일부만 있으며, 3건만 모두 등록된 상태다. 고급 matcher의 독립 증분은
choseong 3 TP뿐이었고 fuzzy는 TP 없이 occurrence FP 2개를 추가했다. 따라서 PF-007의 첫
우선순위는 matcher 확대가 아니라 빈도 높은 missing canonical term·명시적 Alias 후보 평가다.

공개 집계는 `evaluation/results/pf005-batch-001-adjudicated.report.json`에 저장했다. 보호 원문,
case ID, canonical term, reviewer ID와 전체 ablation case 결과는 Git·배포물에 넣지 않는다.
이 결과는 단일 출처의 첫 100건이며 `gold_ready=false`다. PF-005의 500 positive·2,000 negative,
출처 편향 완화와 hidden evaluation 완료를 의미하지 않는다.

## PF-005 종료 전 남은 작업

1. 다음 100건 primary/secondary batch를 생성해 같은 독립 판정 절차 반복
2. 첫 batch의 missing canonical 상위 cluster를 PF-007 후보로 평가하고 candidate별 positive 1건,
   등록 표현·승인 변형이 없는 hard-negative 2건 이상 고정
3. 핵심 positive slice별 30건, 등록 표현을 포함한 정상 substring·인용/설명·사용자명/게임
   문맥 positive와 등록 표현이 없는 철자 유사 negative 확보
6. 단일 출처 100% 편향 완화
7. corpus custodian이 별도 hidden evaluation을 구축하고 PF-004 누출 검사를 실행
8. 확정 positive 500건·hard-negative 2,000건으로 전체 및 slice별 지표 재생성

이 조건 전에는 #7을 완료로 닫거나 2,500건을 실서비스 gold corpus라고 부르지 않는다.
