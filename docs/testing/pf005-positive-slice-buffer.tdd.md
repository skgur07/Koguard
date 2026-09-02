# PF-005 positive 변형 slice buffer TDD 기록

## 문제

기존 확정·targeted 근거를 합쳐도 Alias·Keyboard·Mixed-gap positive는 각 1건, Jamo·Repeated는
각 3건, Separator 4건, Whitespace 2건, Unicode 0건이다. 외부 댓글의 남은 review에서 이 변형을
기다리는 방식은 출처 분포와 우연에 의존하고, detector 결과로 queue를 고르면 평가 편향이 생긴다.

## RED

- 기존 curated base·hard-negative buffer와 direct·NFKC+casefold가 겹치지 않는 480건 생성 테스트
- 8개 설계 slice마다 positive-target 30건과 정상 decoy 30건인지 확인하는 테스트
- corpus의 label·span·slice가 판정 의도를 노출하지 않는지 확인하는 테스트
- 생성 corpus validator, 결정성, stable opaque ID와 MIT source 계약 테스트
- 공개 report와 CLI 출력에 원문·case ID·canonical·reviewer ID가 없는지 확인하는 테스트

## GREEN

`evaluation.curated_policy_intake --kind positive-slice-buffer`를 추가했다. 명시적 Alias, 두벌식
ASCII 입력, compatibility Jamo, NFD·format·cluster Unicode, 모음 연장 반복, 설정된 separator,
1~3칸 공백과 separator+공백 혼합 표면을 프로젝트가 직접 작성한다. 생성에 detector prediction,
matcher method, upstream label이나 기존 annotation을 사용하지 않는다.

결과는 Alias, Keyboard, Jamo, Unicode, Repeated, Separator, Whitespace, Mixed-gap마다
positive-target 30건과 정상 decoy 30건으로 총 480건이다. 모든 사례는 `review`, 빈 expected
matches, `unadjudicated-intake`, tuning으로
생성된다. 공개 corpus는 MIT project-authored 자료지만 설계 의도를 gold label로 간주하지 않는다.

## 생성 후 진단

queue를 고정한 뒤에만 현재 profile을 별도 진단했다. 240개 positive-target 중 `balanced`는
63건, `aggressive`는 180건을 탐지했고 정상 decoy 240건의 탐지는 두 profile 모두 0건이었다.
`aggressive`의 미탐 60건은 Whitespace 30건과 Mixed-gap 30건이다. 현재 gap matcher가 변형 뒤에
붙은 한글 조사까지 포함된 입력을 놓치는 경계를 보여준다. 이 수치는 설계 의도 기준의
post-generation 진단이며 독립 annotation precision·recall이나 hidden 성능이 아니다.

2026-09-01 조사 경계 보강 후 같은 고정 설계를 다시 진단했다. `balanced`는 63/240으로
유지됐고 `aggressive`는 240/240으로 늘었으며, 두 profile의 정상 decoy 탐지는 계속 0/240이다.
이 전후 비교도 독립 판정 전 설계 label 기준 진단이며 gold나 hidden 수치가 아니다.

## 독립 판정 결과

2026-09-02 두 reviewer가 detector 출력과 서로의 결과를 보지 않고 480건을 독립 판정했다.
두 판정은 positive 240건, hard-negative 240건에 전부 합의했고 review·불일치·privacy 제외는
0건이었다. 따라서 제3 reviewer의 재심 대상은 없었다. 8개 실제 slice는 각각 60건이며 확정본은
validator를 통과했다.

확정 label로 다시 측정한 문장 기준 strict·balanced는 TP/FP/FN/TN `63/0/177/240`, aggressive는
`240/0/0/240`이다. R1 전 aggressive TP 180건에서 늘어난 60건은 Whitespace·Mixed-gap 각
30건이다. 첫 occurrence 집계의 Alias 12건 불일치는 span이나 탐지 결과가 아니라 annotation의
canonical 선택 차이였다. 두 reviewer가 packaged Alias 매핑으로 Alias positive 30건씩 독립
재감사해 같은 12건을 교정했고 span·label 오류는 0건이었다. 재측정한 aggressive occurrence
TP/FP/FN은 `240/0/0`이다. 이 결과는 targeted tuning 근거이며 2,763건 tuning이나 hidden 성능에
합산하지 않는다.

```powershell
uv run python -m evaluation.curated_policy_intake --kind positive-slice-buffer
uv run python -m evaluation.corpus_validator `
  evaluation\corpus\tuning\curated-positive-slice-buffer-v1.json
uv run pytest tests/test_curated_policy_intake.py
```
