# 명시적 Alias 매칭 TDD 기록

작성일: 2026-08-05

## 목표

전체 공백 제거 또는 모든 자모 조합 확장 없이, 실제 누락으로 확인된 축약 표현만 구조화된
Alias 규칙으로 탐지한다. 원문 span, Whitelist 구간 보호, 토큰 경계, 설정별 비활성화 계약은
기존 엔진과 동일하게 유지한다.

## 공개 계약

- `EngineConfig.alias_matching`의 기본값은 `True`이며 정확한 `False`로 독립 비활성화한다.
- 결과의 `MatchMethod`는 `ALIAS`다.
- `exact_token`은 독립된 영숫자 토큰 전체에만 일치한다.
- `token_prefix`는 토큰 시작에서 일치하고, 뒤에는 한글 음절 접미부만 허용한다.
- Alias의 canonical term은 같은 사전의 blacklist 항목이어야 한다.
- Alias 검색은 정규화 view와 원문 `source_spans`를 사용하며 공백이나 구두점을 전역 삭제하지
  않는다.

## RED

- `ㅈ같네`, `ㅈ됐네`, `ㅄ`, `ㅈㄲ`, `ㅅㅄㄲ` 양성 사례와 공백·부분 토큰·정상 문장 음성
  사례를 먼저 추가했다.
- 설정 OFF, Whitelist 겹침, NFC/NFKC, NFKC 확장 원문 span, 구조화 파일 오류 계약을 함께
  고정했다.
- 대상 5개 테스트 파일 실행 결과: 수집 단계 3개 오류.
- 실패 원인: 아직 공개 API에 `AliasMode`와 `AliasRule`이 없어 alias 테스트 모듈을 import할 수
  없다. 새 계약이 구현되지 않았기 때문에 발생한 의도한 RED다.

## 출처 경계

규칙 후보 조사에는 `Tanat05/korean-profanity-resources`를 참고한다. 저장소가 자체
`slang.csv`의 라이선스를 `확인 필요`로 표시하므로 전체 데이터는 복사하거나 포함하지 않는다.
이번 규칙은 사용자가 제시한 실제 누락과 최소 회귀 사례만 Koguard 정책으로 수동 선정한다.
