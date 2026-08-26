# PF-005 hard-negative buffer batch-001 검증 기록

## 범위

기존 intake와 direct/NFKC+casefold 중복이 없는 1,000건 buffer에서 500건을
`source-round-robin-sha256-v1`로 선택했다. 선택량은 Koguard curated 100, KOTE 134, Curse 133,
Korean Hate Speech 133이며 detector prediction과 upstream label을 사용하지 않았다.

## 독립 판정

- Primary: positive 2, hard-negative 483, review 15
- Secondary: positive 8, hard-negative 465, review 27
- 완전 consensus: 48
- 불일치와 제3 판정 대상: 452
- 제3 판정 해결: 442
- 제3 판정 뒤 unresolved: 10
- 최종: positive 12, hard-negative 471, review 17
- privacy exclude/pending: 0/0

합의는 label뿐 아니라 original span, canonical term과 slice까지 같아야 한다. 제3 reviewer는 앞선
annotation 값을 보지 않고 불일치 case 집합과 blinded 원문만 판정했다. 보호 원문, case ID,
canonical term과 reviewer ID는 Git과 공개 report에 포함하지 않았다.

## 확장 tuning 재측정

기존 2,500건 보호 corpus와 이번 500건을 함께 평가했다. review 1,545건을 제외한 확정 표본은
positive 389, hard-negative 1,066으로 총 1,455건이다.

| profile | 문장 TP/FP/FN/TN | 문장 recall | occurrence TP/FP/FN | occurrence recall |
| --- | --- | ---: | --- | ---: |
| strict | 233/0/156/1,066 | 59.9% | 304/37/344 | 46.9% |
| balanced | 243/0/146/1,066 | 62.5% | 316/41/332 | 48.8% |
| aggressive | 253/15/136/1,051 | 65.0% | 320/70/328 | 49.4% |

balanced는 strict 대비 문장 TP +10·FP +0, occurrence TP +12·FP +4다. 문장 FP rate와 성능
예산은 통과하지만 occurrence FP 증분 0 조건 때문에 전체 profile gate는 계속 실패한다.

## 검증 명령

```powershell
uv run python -m evaluation.review_queue_planner <protected buffer> --limit 500 <outputs>
uv run python -m evaluation.annotation_workflow export <protected queue> <reviewer outputs>
uv run python -m evaluation.annotation_workflow merge <protected paths>
uv run python -m evaluation.annotation_workflow adjudicate <protected paths>
uv run python -m evaluation.corpus_validator <protected adjudicated corpus>
uv run python -m evaluation.ablation_runner --corpus <base corpus> <new batch> --iterations 100 --warmups 10
uv run python -m evaluation.profile_report --source-ablation <protected report>
uv run pytest
```

## 남은 제한

- 목표까지 positive 111건과 hard-negative 934건이 부족하다.
- 기존 intake review 1,528건, 이번 batch review 17건과 buffer 미선택 500건이 남았다.
- PF-007 후보는 확장 표본에서 별도 재평가해야 한다.
- KOTE·Korean Hate Speech privacy·권리 경계와 독립 hidden evaluation은 완료되지 않았다.
