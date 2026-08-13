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
