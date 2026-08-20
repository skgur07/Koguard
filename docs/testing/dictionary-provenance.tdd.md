# PF-006 dictionary provenance TDD 기록

## Red

다음 실패 계약을 `tests/test_dictionary_provenance.py`에 먼저 추가했다.

- schema의 닫힌 source·candidate 계약과 core/AI 계층
- packaged literal·Alias의 완전 대응
- Unicode normalized surface 중복과 잘못 선언된 NFKC 값
- Alias canonical과 packaged literal의 불일치
- 미승인 라이선스·재배포 불가·미승인 review·평가 근거 없는 승격
- 등록 core literal을 포함한 hard-negative
- 실패 출력의 candidate surface 비노출

구현 전 테스트 수집은 `ModuleNotFoundError: evaluation.dictionary_provenance`로 실패했다.

## Green

`dictionary-provenance.schema.json`, 오프라인 validator와 기존 63개 packaged 후보 manifest를
추가했다. source 2개, literal 58개, Alias 5개를 실제 packaged file과 양방향으로 비교한다.

## Refactor

라이선스 문자열과 재배포 boolean만으로는 검토 완료를 표현할 수 없어 `license_status`를 별도
필드로 추가했다. 승인 결정 근거와 평가 reference도 packaged 승격 필수 조건으로 강화했다.
오류는 candidate ID만 식별자로 사용하도록 유지했다.

## 2026-08-18 사전 승격 회귀

소유자가 승인한 한국어 literal 4개와 직접 선별한 소문자 로마자 literal 3개를 먼저 테스트에
추가해 18건의 실패를 확인했다. packaged file과 provenance를 함께 갱신한 뒤 source 3개,
candidate 73개, packaged literal 65개, Alias 5개의 양방향 검증이 통과했다. PF-007 후보 중
승격하지 않은 3개는 `candidate` 상태를 유지한다.

## 2026-08-19 다중 출처 intake 기반 추가 승격

기존 92건 독립 consensus를 2,500건 다중 출처 review intake에 보존하고 남은 PF-007 후보 3개를
재평가했다. tuning gate를 통과하고 소유자의 문맥 무관 차단 정책에 맞는 literal 2개를 먼저
실패 테스트로 고정한 뒤 packaged file과 provenance를 함께 갱신했다. candidate 73개,
packaged literal 67개, Alias 5개가 양방향으로 일치하며 PF-007 후보 1개는 gate 실패로 계속
`candidate` 상태를 유지한다.
