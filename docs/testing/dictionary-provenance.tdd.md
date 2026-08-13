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
