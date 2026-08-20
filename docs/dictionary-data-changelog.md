# 사전 데이터 변경 기록

사전 변경은 raw term 개수가 아니라 provenance, 독립 평가와 증분 TP·FP·FN으로 판단한다. 이
문서는 `evaluation/dictionary-provenance.v1.json`의 안정 candidate ID를 기준으로 변경 이력을
연결한다.

## v1 — 기존 packaged data provenance 고정

- 기준일: 2026-08-13
- manifest: `koguard-default-dictionary-v1`
- packaged literal: 58개 (`badwords.txt` 56개 + Alias canonical 2개)
- packaged Alias: 5개
- source: Koguard 직접 선별 1개, MIT Korcen 고정 revision 1개
- AI candidate: 0개
- pending review: 0개
- 정책: 등록 literal·승인 Alias의 문맥 무관 core positive
- 회귀 근거: `tests/corpus/exact_cases.json`, `tests/corpus/alias_cases.json`,
  `docs/accuracy-baseline.md`
- 독립 실서비스 지표: PF-005 consensus 대기. 이 inventory 고정 자체는 recall 개선 주장으로
  사용하지 않는다.

## PF-007/2026-08-13 — 첫 FN cluster 후보 평가

- candidate IDs: `core.literal.pf007.001` ~ `.007`
- source: `curse-detection-data-ff241621`, MIT 고정 revision
- 변경: 7개 모두 `candidate`; packaged data 변경 없음
- target layer: core
- 독립 consensus 근거: `evaluation/results/pf005-batch-001-adjudicated.report.json`
- tuning 전: sentence TP/FP/FN/TN 37/0/25/30, occurrence TP/FP/FN 41/13/69
- 7개 결합 후보: sentence 47/0/15/30, occurrence 61/12/49
- 증분: sentence TP +10, FP +0; occurrence TP +20, FP -1
- 개별 tuning gate: 5개 통과, 2개 유보
- report: `evaluation/results/pf007-top-candidates.report.json`
- 권리: MIT 승인 source에서 독립 판정한 후보이며 provenance 기록 완료
- NOTICE 변경: 없음. 아직 runtime packaged data가 아니므로 배포 고지는 변경하지 않음
- 한계: 단일 출처 첫 100건 tuning 결과이며 hidden evaluation 0건. 통과 후보도 즉시 승격하지
  않고, 실패 후보의 표면형·canonical·matcher 경계를 재검토한 뒤 hidden gate를 통과해야 한다.

`tuning_gate_passed`는 packaged 승격이나 제품 recall 보장을 뜻하지 않는다. candidate별 positive
support 1건 이상, 독립 hard-negative 2건 이상, occurrence TP 순증가와 sentence FP 무증가만
확인한 중간 상태다.

## v2/2026-08-18 — 소유자 승인 Exact Match 확대

- 승격: `core.literal.pf007.003` ~ `.006` 4개
- 직접 추가: `core.literal.curated.033` ~ `.035` 소문자 로마자 literal 3개
- packaged literal: 65개 (`badwords.txt` 63개 + Alias canonical 2개)
- packaged Alias: 5개
- 전체 candidate record: 73개, 이 중 PF-007 candidate 3개는 계속 보류
- source: MIT Koguard 직접 선별, MIT Korcen, MIT `2runo/Curse-detection-data`
- 검토 근거: PF-005 독립 이중 검토·조정, PF-007 증분 결과, 2026-08-18 소유자 승인
- 정책: 문맥과 무관한 substring Exact Match. 중의적 복합어 오탐도 core positive로 취급
- 로마자 경계: `sibal`, `ssibal`, `shibal` 소문자 literal만 지원하며 일반 로마자 변환·case
  folding은 추가하지 않음
- 외부 고지: `CURSE-DETECTION-DATA-MIT.txt`를 wheel과 sdist에 포함
- 한계: `따먹다`는 PF-007 개별 tuning에서 occurrence 순증가가 없었지만 소유자 정책으로
  승격했다. hidden evaluation은 아직 없으므로 rollback 기준은 후속 독립 corpus에서 정한다.

동일한 92건 provisional tuning corpus 재측정에서 `balanced` 문장 recall은 58.1%에서 62.9%,
`aggressive`는 59.7%에서 66.1%로 상승했다. hard-negative 30건의 문장 FP는 여전히 0이지만
표본이 작으므로 실서비스 오탐률로 일반화하지 않는다. 최신 공개 집계는
`evaluation/results/pf009-profile-evaluation.report.json`에 기록한다.

## v3/2026-08-19 — 다중 출처 intake 기반 보류 후보 재평가

- 승격: `core.literal.pf007.001`, `.002` 2개
- 보류: `core.literal.pf007.007` 1개
- packaged literal: 67개 (`badwords.txt` 65개 + Alias canonical 2개)
- packaged Alias: 5개
- 전체 candidate record: 73개, 이 중 PF-007 candidate 1개는 계속 보류
- source: MIT `2runo/Curse-detection-data`; KOTE·BEEP·Koguard curated intake는 corpus 구성의
  출처 편향 완화에만 사용하고 그 원문이나 term을 사전에 복사하지 않음
- 독립 consensus 근거: 기존 92건(positive 62, hard-negative 30)의 이중 검토·조정 결과
- 변경 전: sentence TP/FP/FN/TN 41/0/21/30, occurrence TP/FP/FN 46/13/64
- 세 후보 결합: sentence 47/0/15/30, occurrence 61/12/49
- `.001`: sentence TP +6/FP +0, occurrence TP +12/FP +4로 tuning gate 통과
- `.002`: sentence TP +0/FP +0, occurrence TP +2/FP -2로 tuning gate 통과
- `.007`: sentence TP +0/FP +0, occurrence TP +1/FP +1로 gate 실패하여 보류
- 정책 영향: `.001` 승격에 따라 `새끼손가락`처럼 표면형을 포함한 정상 복합어도 기본
  `balanced`에서 탐지하며, 이는 문맥 무관 필터링이라는 소유자 정책에 따른 의도된 결과
- report: `evaluation/results/pf007-balanced-candidates.report.json`
- 권리: 승격 literal은 고정 MIT source와 기존 독립 판정에서 유래하며 NOTICE의 승인 개수를
  4개에서 6개로 갱신; 다른 외부 corpus 원문은 배포하지 않음
- 한계와 rollback: 아직 hidden evaluation 0건이다. hidden 문장 FP 예산 초과 또는 정상
  복합어 차단 비용이 제품 정책과 맞지 않으면 `.001`을 우선 rollback한다.

## 변경 기록 template

새 변경은 아래 항목을 복사해 추가한다.

```markdown
## <version/date> — <cluster or decision>

- candidate IDs:
- source IDs/revisions:
- 변경: candidate / packaged / rejected
- target layer: core / ai-candidate
- 독립 consensus 근거:
- tuning report와 변경 전 TP·FP·FN:
- tuning report와 변경 후 TP·FP·FN:
- hidden report의 원문 없는 집계 위치:
- 라이선스·재배포 판정:
- NOTICE 변경:
- 알려진 한계와 rollback 조건:
```

hidden·private 원문이나 canonical term 목록을 이 문서에 복사하지 않는다. 공개할 수 있는 aggregate
report 경로 또는 hash만 기록한다.
