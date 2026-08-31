# PF-005 초성 occurrence 재감사와 slice 우선 queue 검증 기록

## 초성 occurrence FP 재감사

batch-004 반영 뒤 balanced의 strict 대비 occurrence FP 증분은 7건이었다. 해당 사례는 모두
policy positive 문장이므로 sentence FP가 아니라 기대 span/canonical과 다른 추가 occurrence다.
5건과 2건의 보호 corpus로 나눠 prior label·span·slice를 제거하고 독립 이중 검토했다. 두
reviewer는 7건 모두 positive로 판정했고, base의 span-level 불일치 2건만 제3 reviewer가 해소했다.
privacy exclude·pending과 계약 오류는 0건이다.

재감사 적용 뒤 표본 수와 문장 지표는 변하지 않았다. occurrence 지표는 다음과 같다.

- strict TP/FP/FN: 554/37/420
- balanced TP/FP/FN: 584/39/390
- strict 대비 balanced: TP +30, FP +2
- balanced occurrence recall: 60.0%

따라서 annotation 누락·불일치가 설명하던 FP 5건은 제거됐고 TP 증분도 25건에서 30건으로
늘었다. 남은 2건은 재감사 후에도 기대 occurrence가 아니므로 전체 FP 증분 0 gate는 계속
실패한다.

## slice coverage와 다음 queue

확정 corpus에서 slice별 positive 30건·hard-negative 2건 목표의 부족분을 aggregate로 계산했다.
대표 positive 부족분은 Alias 29, Keyboard 29, Mixed-gap 29, Whitespace 28, Phonetic 28,
Jamo·Repeated·Separator·Domain-term 각 27, Token-boundary 21건이다. Choseong positive는 30건을
충족했지만 hard-negative가 0건이다. 사례는 여러 slice에 속할 수 있으므로 합계는 전체 건수와
일치하지 않는다.

미검토 419건에서 detector prediction·upstream label·기존 annotation을 사용하지 않고 텍스트의
형태만으로 다음 120건을 우선 배치했다. source round-robin 결과는 KOTE·Curse·Korean Hate
Speech 각 40건이며 과거 queue overlap은 0건이다. 선택 120건 중 107건이 하나 이상의 표면
신호를 가진다.

- 초성 연속 66건
- compatibility Jamo 74건
- 반복 문자 76건
- 한글 사이 separator 25건
- 단일 한글 gap 12건
- ASCII token 4건
- modern Jamo 1건

이 queue는 부족 slice 후보 발굴용 targeted sample이다. 일반 tuning 정확도나 hidden 성능을
추정하는 표본으로 사용하지 않는다. 원문 queue와 annotation은 보호 경로에만 두며 공개 파일은
aggregate report로 제한한다.

## 독립 판정 결과

120건을 서로의 결과를 보지 않는 두 역할로 판정하고, 최초 불일치만 별도의 제3 역할이
재심했다. 개인정보 검토 제외·pending은 0건이다. 최초 완전 합의는 27건, 불일치는 93건이었다.
제3 재심으로 80건을 확정하고 13건은 보류했다. 두 reviewer가 모두 보류한 18건은 현재
adjudication 계약의 재심 대상이 아니므로 최종적으로 positive 26건, hard-negative 63건,
review 31건이다. 표면형 후보의 초기 합의율이 낮았다는 사실과 남은 review를 숨기지 않고
`gold_ready=false`를 유지한다.

확정 89건은 기존 2,763건 tuning 정확도 표본에 합치지 않았다. 별도 slice 보강 근거로만 더하면
Choseong positive는 30→36, Separator positive/hard-negative는 3/0→4/13,
Repeated hard-negative는 0→38, Whitespace hard-negative는 0→4가 된다. 반면 Alias·Keyboard·
Mixed-gap positive는 여전히 각 1건, Unicode positive는 0건이고, Separator·Repeated·Whitespace
positive도 각각 4·3·2건에 그쳐 positive 변형 사례 보강이 다음 핵심 작업이다.

공개 근거는 다음 세 aggregate-only 파일이다.

- `evaluation/results/pf005-slice-priority-batch-001.report.json`
- `evaluation/results/pf005-slice-priority-batch-001-adjudicated.report.json`
- `evaluation/results/pf005-slice-coverage.report.json`
