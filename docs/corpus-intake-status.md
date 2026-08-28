# PF-005 초기 corpus 구축 상태

- 기준일: 2026-08-28
- 상태: 다중 출처 balanced intake와 hard-negative buffer 1,000건, 중복 없는 balanced
  batch-003·004 독립 판정·제3 판정 완료, PF-005 수량 기준 충족, 전체 gold corpus 미완료
- annotation workflow: 이중 판정·불일치 제3 판정 구현 및 실제 batch 검증 완료
- 로컬 source별 tuning 후보: 5,250건(기존 4,250건 + 중복 없는 buffer 1,000건)
- balanced tuning composition: 2,500건
- hard-negative 중심 review buffer: 1,000건
- 확정 positive: 639건
- 확정 hard-negative: 2,124건
- 판정 대기: 737건(기존 intake 700건, buffer 두 batch 37건)
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
| Koguard-policy finalized | 2,763/3,500 |
| exact span annotated positive | 639건, 975 occurrence |

2026-08-19에는 공개 재배포 조건을 확인한 독립 원출처 두 개와 Koguard 직접 작성 정책 slice를
추가했다. `searle-j/KOTE` train 40,000건 중 750건, `kocohub/korean-hate-speech` train
7,896건 중 label strata별 250건씩 750건, Koguard 직접 작성 review 250건을 고정했다. KOTE는
MIT, Korean Hate Speech는 CC-BY-SA-4.0이며 source revision, artifact·license SHA-256을 source
spec v2에 기록했다. 원문은 수동 privacy review 전까지 계속 Git·sdist·wheel에서 제외한다.

최종 review composition은 첫 batch 확정 92건을 보존한 2runo 750건, KOTE 750건, Korean Hate
Speech 750건, Koguard curated 250건으로 총 2,500건이다. 출처별 비중은 `30%/30%/30%/10%`,
직접·NFKC+casefold 중복은 0건이며 30% 상한을 통과했다. 이 수치는 source 편향 gate만 통과한
것이고, 독립 판정 뒤에도 남은 737건을 gold로 승격하거나 실서비스 분포를 보장하지 않는다.

## 재현성

- source revision: `ff241621e103b6f220d30de324d0d07987887308`
- source artifact SHA-256:
  `1c3489417e4972dbbbdde19cc47bb8638292891f7f1a443ecbdc2e3c6843545a`
- upstream LICENSE SHA-256:
  `5cb5b18cc855e245f8e299b931a1203479a56fd79a752b102d623056ba5d7c2c`
- generated corpus SHA-256:
  `c26c942a3d825e1667d2d520d41fcda6f03a4e07d81ad4d8ba84038096125b83`
- intake report v2 canonical-LF SHA-256:
  `54319c0e838ae2f61a7ed601ceefb951ebc84300888ed746c81ac8672020603f`
- split manifest v2 canonical-LF SHA-256:
  `06dc923ece416dee03cf6db984b319daa6290b7a1b3e212f2f8c0cbb042f846d`
- KOTE intake report canonical-LF SHA-256:
  `acf3420143f20be0b7131d223473f5817d72971d8d630f36ebaf439c19be89f7`
- Korean Hate Speech intake report canonical-LF SHA-256:
  `ac1bdffdcff4291eff4633e6ab36254ace2c9d4e3e73d1fd485e3e1a1ab915f4`
- curated policy intake report canonical-LF SHA-256:
  `55cdf26d6102dd00776f51d616e660d169821abe6fe82a9f877082b9272bfd15`
- balanced composition config/report canonical-LF SHA-256:
  `969c360992fba7ebbe4719c76a6efe681c3cfce0de3d60bf649b9608b6c94465` /
  `685d537b8e97409886bb30801b62a9709340812903758d7c0bfca195c70c4081`

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

uv run python -m evaluation.corpus_intake `
  evaluation\sources\kote.v1.json C:\artifacts\kote-train.tsv `
  --output evaluation\corpus\tuning\kote-review-intake-v1.json `
  --report evaluation\results\kote-review-intake-v1.report.json

uv run python -m evaluation.corpus_intake `
  evaluation\sources\beep-korean-hate-speech.v1.json C:\artifacts\beep-train.tsv `
  --output evaluation\corpus\tuning\beep-review-intake-v1.json `
  --report evaluation\results\beep-review-intake-v1.report.json

uv run python -m evaluation.curated_policy_intake

uv run python -m evaluation.corpus_composer `
  evaluation\compositions\pf005-balanced-review-intake.v1.json `
  --output evaluation\corpus\tuning\pf005-balanced-review-intake-v1.json `
  --report evaluation\results\pf005-balanced-review-intake-v1.report.json
```

## 편향과 품질 한계

balanced composition은 어느 한 source도 30%를 넘지 않아 이슈의 수치상 출처 편향 조건을
충족한다. 다만 세 외부 자료가 모두 온라인 댓글이고, KOTE와 Korean Hate Speech의 플랫폼·수집
시기·annotation 목적이 Koguard lexical 정책과 다르므로 실서비스 대표성을 보장하지 않는다.
Koguard 직접 작성 250건도 정책 경계와 slice를 보강하는 합성 자료이지 실사용 댓글이 아니다.

`unadjudicated-intake`는 실제 평가 slice가 아니라 판정 대기 상태다. 확정 2,763건은 실제 slice별
TP·FP·FN을 계산할 수 있지만, review 737건은 runner가 자동 평가하지 않는다. 따라서 현재
집계는 확정된 provisional tuning 일부만 설명하며
3,500건 전체나 실서비스 gold 수치가 아니다.

선택 전 전체 5,825건에서 이메일·URL·전화번호·주민번호형·IP·6자리 이상 숫자·@handle 후보
25건을 자동 제외했다. 이 검사는 명백한 패턴의 방어선일 뿐 이름이나 간접 식별자를 보장하지
못하므로 사람의 privacy review가 끝나기 전에는 gold로 승격하지 않는다.

수동 privacy review가 끝나지 않은 외부 원문을 공개하지 않고 runtime 크기에 평가 원문 비용도
전가하지 않도록 외부 intake와 balanced composition은 Git, wheel, sdist에서 모두 제외한다. 로컬 생성 artifact는
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

## 2026-08-20 balanced 500건 독립 판정 결과

서로 결과를 보지 않은 Primary와 Secondary가 balanced composition의 다음 500건을 판정했다.
두 검토자의 label은 464/500에서 일치했지만 span·canonical term·slice까지 같은 완전 합의는
113/500이었다. 공개 workflow는 세부 annotation 차이도 불일치로 취급했고, 제3 검토자가
불일치 387건을 이전 결과 없이 독립 판정했다.

| 항목 | 값 |
| --- | ---: |
| privacy 이중 검토 완료 | 500 |
| 최초 완전 consensus | 113 |
| 제3 판정 대상 | 387 |
| 제3 판정 확정 | 334 |
| 제3 판정 후 review 유지 | 53 |
| 최종 positive | 202 |
| 최종 hard-negative | 242 |
| 최종 review | 56 |

기존 확정 92건과 합친 protected tuning corpus는 positive 264건, hard-negative 272건,
review 1,964건이며 positive 정답 occurrence는 480개다. 공개 집계는
`evaluation/results/pf005-balanced-batch-001-adjudicated.report.json`에 저장했고 원문, case ID,
canonical term, reviewer ID는 포함하지 않았다.

확정 536건의 profile 재측정에서 `strict` 문장 recall은 51.1%(FP 0/272), `balanced`는
53.4%(FP 1/272), `aggressive`는 56.4%(FP 2/272)였다. `balanced`는 strict 대비 문장 TP 6건을
추가했지만 FP도 1건 늘어 현재의 FP 증분 0 gate를 통과하지 못했다. 이 결과는 hidden 평가가
아니며 기본 profile을 즉시 바꾸는 근거로 사용하지 않는다.

보류 중인 PF-007 literal 1개는 새 tuning에서 문장 TP/FP 변화 없이 occurrence TP +2, FP -2로
gate를 통과했다. 다만 hidden 검증 전에는 packaged data로 승격하지 않고 candidate 상태를 유지한다.

## 2026-08-25 정책 재감사와 balanced batch-002

Choseong 증분 FP로 분류됐던 3건은 기존 label·detector 결과를 제거한 상태에서 두 역할이 각각
검토했고 세부 span·slice 불일치 3건을 제3 역할이 판정했다. 최종 3건은 모두 positive였으며,
보호 corpus 적용 전이는 `positive->positive` 2건과 `hard-negative->positive` 1건이다. 공개
집계는 `evaluation/results/pf005-policy-reaudit-v1-adjudicated.report.json`과
`evaluation/results/pf005-policy-reaudit-v1-apply.report.json`에 저장했다.

다음 500건은 네 출처에서 각각 125건을 detector·upstream label 없이 결정적으로 선택했다.
두 역할의 완전 consensus는 207건, 불일치는 293건이었고 제3 판정으로 281건을 확정하고 12건을
review로 유보했다. 최종 batch는 positive 112건, hard-negative 324건, review 64건이며 privacy
제외는 0건이다. 전체 protected tuning corpus는 positive 377건, hard-negative 595건, review
1,528건이다. 공개 집계는
`evaluation/results/pf005-balanced-batch-002-adjudicated.report.json`에 저장했다.

확정 972건 재측정에서 `strict` 문장 TP/FP/FN/TN은 231/0/146/595, `balanced`는
241/0/136/595, `aggressive`는 250/10/127/585다. balanced 문장 recall은 63.9%이고 strict 대비
TP +10·FP +0이다. occurrence는 balanced 314/41/320, recall 49.5%이며 strict 대비
TP +12·FP +4라서 전체 FP 증분 0 gate는 실패한다.

PF-007의 보류 literal 1개는 같은 972건에서 문장 TP/FP 변화 없이 occurrence TP +2·FP -2로
다시 gate를 통과했다. 결과는
`evaluation/results/pf007-balanced-batch-002-candidates.report.json`에 기록했으며 hidden 검증
전에는 candidate 상태를 유지한다.

## 2026-08-25 hard-negative 중심 review buffer

기존 2,500건만으로는 unresolved를 허용하면서 positive 500·hard-negative 2,000건 목표를
동시에 달성할 여유가 없었다. 같은 고정 artifact와 라이선스를 사용해 Curse label `0`의 다음
300건, BEEP `none`의 다음 300건, label이 없는 KOTE의 다음 300건을 확장 intake로 만들고,
Koguard가 직접 작성한 hard-negative-target 100건을 추가했다. upstream label과 설계 의도는
review 후보 targeting에만 사용하며 생성 label은 전부 `review`다.

`evaluation.review_buffer_planner`는 각 확장 intake에서 기존 source intake와 direct 및
NFKC+casefold 중복을 제거했다. 최종 buffer는 Curse 300, KOTE 300, BEEP 300, Koguard curated
100으로 총 1,000건이며 최대 출처 비중 30%, 기존 intake overlap 0건이다. 원문 corpus는
`evaluation/annotation-work/`와 ignored tuning 경로에만 두고, 공개 집계는
`evaluation/results/pf005-hard-negative-buffer-v1.report.json`에 저장했다.

이 buffer는 hard-negative gold 1,000건이 아니다. hard-negative-target 근거가 있는 700건과
label 없는 독립 분포 KOTE 300건으로 구성된 blinded review pool이며, 모든 사례는 이중 판정과
불일치 제3 판정을 거쳐야 한다.

## 2026-08-26 hard-negative buffer batch-001

buffer에서 source round-robin으로 500건을 선택했다. Koguard curated 100건, KOTE 134건,
Curse 133건, Korean Hate Speech 133건이며 detector prediction과 upstream label은 선택과 reviewer
입력에 사용하지 않았다. 두 독립 reviewer의 완전 consensus는 48건이고 불일치 452건을 제3
reviewer가 독립 판정했다. 최종 batch는 positive 12건, hard-negative 471건, review 17건이며
privacy 제외·대기는 0건이다. 공개 집계는
`evaluation/results/pf005-hard-negative-batch-001-adjudicated.report.json`에 저장했다.

기존 확정 결과와 합친 평가 가능 표본은 positive 389건, hard-negative 1,066건으로 총 1,455건이다.
`balanced` 문장 TP/FP/FN/TN은 243/0/146/1,066, recall 62.5%이고 occurrence TP/FP/FN은
316/41/332, recall 48.8%다. strict 대비 문장 TP +10·FP +0, occurrence TP +12·FP +4로 profile
gate 실패 원인은 그대로다. 목표까지 positive 111건과 hard-negative 934건이 더 필요하다.

## 2026-08-26 hard-negative buffer batch-002

첫 queue를 `--exclude-corpus`로 제외한 뒤 남은 500건을 선택해 두 batch의 교집합이 0건임을
검증했다. 출처 구성은 KOTE 166건, Curse 167건, Korean Hate Speech 167건이다. 두 독립
reviewer의 완전 consensus는 16건이고 불일치 484건을 제3 reviewer가 판정했다. 최종 batch는
positive 29건, hard-negative 451건, review 20건이며 privacy 제외·대기는 0건이다. 공개 집계는
`evaluation/results/pf005-hard-negative-batch-002-adjudicated.report.json`에 저장했다.

누적 평가 가능 표본은 positive 418건, hard-negative 1,517건으로 총 1,935건이다. `balanced`
문장 TP/FP/FN/TN은 254/2/164/1,515, recall 60.8%이고 occurrence TP/FP/FN은 326/45/355,
recall 47.9%다. strict 대비 문장 TP +13·FP +0, occurrence TP +13·FP +6이다. hard-negative
문장 FP 2건은 strict와 balanced에 공통이며 전체 occurrence FP 증분 0 gate는 실패한다. 목표까지
positive 82건과 hard-negative 483건이 더 필요하다.

## 2026-08-26 공통 Exact/Alias FP 재감사

strict와 balanced에 공통으로 나타난 `benign-substring` 문장 FP 2건을 이전 label·span·slice 없이
별도 queue로 만들었다. 두 독립 reviewer는 모두 2건을 positive로 판정했고 privacy 승인에도
합의했으며 불일치는 없었다. 이는 matcher 오탐이 아니라 등록 표현을 정상 복합어 문맥 때문에
hard-negative로 둔 이전 annotation이 문맥 무관 core 정책과 충돌한 것이다. 공개 consensus·적용
집계는 `evaluation/results/pf005-common-exact-fp-reaudit-v1-*.report.json`에 저장했다.

재감사 뒤 누적 표본은 positive 420건, hard-negative 1,515건, review 1,565건이다. balanced 문장
TP/FP/FN/TN은 256/0/164/1,515, recall 61.0%이고 occurrence TP/FP/FN은 328/43/355,
recall 48.0%다. strict 대비 문장 TP +13·FP +0, occurrence TP +13·FP +6이다. 목표까지
positive 80건과 hard-negative 485건이 더 필요하다.

## 2026-08-27 balanced batch-003

과거 balanced batch-001 annotation 500건과 batch-002 queue 500건의 교집합 11건을 확인하고,
고유 989건의 합집합을 제외했다. 현재 review 중 과거 검토 사례는 109건이었고 아직 검토하지
않은 1,419건에서 500건을 source round-robin으로 선택했다. 새 queue의 과거 overlap은 0건이며
출처 구성은 Koguard 65건, KOTE·Curse·Korean Hate Speech 각 145건이다.

두 reviewer의 완전 consensus는 136건이고 불일치 364건을 제3 reviewer가 판정했다. 최종 batch는
positive 118건, hard-negative 310건, review 72건이며 privacy 제외·대기는 0건이다. 공개 판정·적용
집계는 `evaluation/results/pf005-balanced-batch-003-*.report.json`에 저장했다.

누적 평가 가능 표본은 positive 538건, hard-negative 1,825건으로 총 2,363건이다. balanced 문장
TP/FP/FN/TN은 351/0/187/1,825, recall 65.2%이고 occurrence TP/FP/FN은 452/43/380,
recall 54.3%다. strict 대비 문장 TP +17·FP +0, occurrence TP +18·FP +6이다. positive 목표는
충족했고 hard-negative 목표까지 175건이 더 필요하다.

## 2026-08-28 balanced batch-004와 공통 FP 재감사

과거 세 batch의 고유 검토 사례 1,489건을 제외하고 아직 검토하지 않은 919건 중 500건을
source round-robin으로 선택했다. 새 queue와 과거 검토 사례의 교집합은 0건이며 KOTE·Curse가
각 167건, Korean Hate Speech가 166건이다. 두 reviewer의 완전 consensus는 174건이고 불일치
326건을 제3 reviewer가 판정했다. 최종 batch는 positive 100건, hard-negative 300건, review
100건이며 privacy 제외·대기는 0건이다.

누적 평가에서 strict와 balanced에 공통인 문장 FP 1건을 발견해 prior label·span·slice 없이
재감사했다. 두 reviewer 모두 positive로 판정했지만 span 세부 불일치를 제3 reviewer가 해소했고,
정책 positive 누락으로 바로잡았다. 최종 누적 평가 가능 표본은 positive 639건, hard-negative
2,124건으로 총 2,763건이며 review 737건은 제외했다. balanced 문장 TP/FP/FN/TN은
440/0/199/2,124, recall 68.9%이고 occurrence TP/FP/FN은 579/44/396, recall 59.4%다. strict
대비 문장 TP +24·FP +0, occurrence TP +25·FP +7이다. PF-005의 500/2,000 수량 기준은
충족했지만 `gold_ready=false`와 occurrence gate 실패는 유지한다.

## PF-005 종료 전 남은 작업

1. 남은 review 737건은 수량 목표와 별개로 slice 보강이나 판정 품질 개선에 필요한 사례부터 확정
2. 확장 corpus의 missing canonical 상위 cluster를 PF-007 후보로 평가하고 candidate별 positive 1건,
   등록 표현·승인 변형이 없는 hard-negative 2건 이상 고정
3. 핵심 positive slice별 30건, 등록 표현을 포함한 substring·인용/설명·사용자명/게임
   문맥 positive와 등록 표현이 없는 철자 유사 negative 확보
4. KOTE·Korean Hate Speech 원문의 수동 privacy 검토와 CC-BY-SA attribution 경계 확정
5. corpus custodian이 별도 hidden evaluation을 구축하고 PF-004 누출 검사를 실행
6. hidden aggregate로 tuning 수치와 독립된 전체·slice별 지표 생성

수량 기준은 충족했지만 이 조건 전에는 #7을 완료로 닫거나 현재 corpus를 실서비스 gold라고
부르지 않는다.
