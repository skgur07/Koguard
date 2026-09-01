# PF-005 조사 suffix 경계 보강 TDD 기록

## 문제

Whitespace·Mixed-gap과 분리 초성 matcher는 전체 영숫자 토큰 끝만 허용했다. 그 결과
`시  발은`, `시 * 발은`, `ㅅ ㅂ이`처럼 승인된 우회 표현 직후에 한국어 조사가 붙으면 욕설
구간을 찾고도 후보를 버렸다. 반대로 끝 경계를 무조건 열면 `시 발표`, `개 새끼손가락` 같은
기존 정상 대조군을 오탐하므로 조사만 제한적으로 허용해야 했다.

## RED

공개 matcher와 engine 경로에 다음 실패 사례를 먼저 추가했다.

- Whitespace: `시  발은`, `개 새끼를`
- Mixed-gap: `시 * 발은`
- segmented Choseong: `ㅅ ㅂ이`
- 원문 `matched_text`와 반열림 span이 조사 앞에서 끝나는지 검증
- `strict`·`balanced`·`aggressive` profile 이동 규칙 검증

구현 전 대상 실행은 새 단위·corpus 사례 6건이 실패했고 기존 59건은 통과했다.

## GREEN

matcher가 입력별 영숫자 경계를 만들 때 닫힌 한국어 조사 목록이 토큰의 남은 부분과 정확히
일치하는 시작 위치도 함께 표시한다. Whitespace와 Mixed projection, Choseong이 같은 경계
판정을 사용하며 match span에는 조사와 뒤 문맥을 포함하지 않는다.

초기 목록에 넣었던 호격 조사 두 개는 보호 tuning에서 Choseong 문장 FP 2건을 만들었다. 현재
요구와 무관한 범위 확장이므로 제거했고, 그 뒤 strict·balanced 지표와 FP가 기존과 같음을
확인했다. 숫자, 앞붙임, 추가 초성, 일반 한글 suffix는 계속 전체 토큰 경계에서 거부한다.

## 검증 결과

- 관련 matcher·profile·corpus: 97 tests 통과
- 전체: 757 tests 통과, branch coverage 95.63%
- 480건 비-gold 설계 진단:
  - balanced positive-target 63/240, decoy 0/240
  - aggressive positive-target 240/240, decoy 0/240
- 보호된 기존 tuning 2,763건:
  - strict 문장 `416/0/223/2124`, occurrence `554/37/420` 유지
  - balanced 문장 `440/0/199/2124`, occurrence `584/39/390` 유지
  - aggressive 문장 TP/FP `454/30 → 455/30`
  - aggressive occurrence TP/FP `588/96 → 589/96`
- 로컬 balanced p95: short-chat 0.0241ms, 최대 입력 4.8955ms로 기존 예산 통과

480건 결과는 아직 설계 label 기준이며 독립 이중 판정 전에는 gold·precision·recall 또는 hidden
성능으로 사용하지 않는다. 기존 balanced occurrence FP 증분 2도 이번 변경과 무관하게 남아 있다.
