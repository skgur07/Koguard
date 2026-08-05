# 영문 자판·호환 자모 입력 TDD 기록

## 사용자 여정

- 사용자는 한글 모드 전환을 잊고 `tlqkf`로 입력한 욕설도 탐지할 수 있다.
- 사용자는 음절을 조합하지 않은 `ㅅㅣㅂㅏㄹ` 입력도 탐지할 수 있다.
- 라이브러리 사용자는 두 단계를 독립적인 정확한 `bool` 설정으로 비활성화할 수 있다.
- 탐지 결과와 Whitelist는 변환된 문자열이 아니라 원문 구간을 기준으로 동작한다.

## RED

- 명령: `.venv\\Scripts\\python.exe -m pytest -c .pytest-empty.ini tests/test_keyboard_input_matching.py tests/test_normalizer.py tests/test_config.py tests/test_models.py -q`
- 결과: `MatchMethod.KEYBOARD`와 `build_dubeolsik_view`가 없어 테스트 수집 단계에서 실패했다.
- 체크포인트: `4aacac7 test: 자판 및 호환 자모 입력 계약 추가`

## GREEN

- 명령: `.venv\\Scripts\\python.exe -m pytest -c .pytest-empty.ini tests/test_keyboard_input_matching.py tests/test_normalizer.py tests/test_config.py tests/test_models.py tests/test_engine.py tests/test_matcher.py tests/test_alias_matching.py -q`
- 결과: `268 passed`
- `pyproject.toml` 첫 줄과 기본 사전의 기존 미커밋 변경 때문에 임시 빈 pytest 설정으로 관련
  테스트를 실행했다. 전체 suite에서 발생한 두 실패는 각각 깨진 TOML과 기존 corpus에 없는
  `시이발` 사전 추가에서 발생했다.

## 테스트 명세

| # | 보장 | 테스트 | 유형 | 결과 |
| --- | --- | --- | --- | --- |
| 1 | `tlqkf`를 `시발`로 탐지하고 원문 span을 보존한다 | `test_composed_input_views_detect_profanity_with_original_span` | 통합 | PASS |
| 2 | `ㅅㅣㅂㅏㄹ`을 `시발`로 탐지하고 원문 span을 보존한다 | 동일 테스트 | 통합 | PASS |
| 3 | 두 단계를 각각 `False`로 끌 수 있다 | `test_keyboard_matching_can_be_disabled_independently`, `test_jamo_composition_matching_can_be_disabled_independently` | 통합 | PASS |
| 4 | 변환된 `시발점` Whitelist가 두 입력형을 보호한다 | `test_composed_input_views_honor_transformed_whitelist` | 통합 | PASS |
| 5 | 두벌식 조합에서 음절 경계, 복합 모음·종성, span을 보존한다 | `test_dubeolsik_view_*`, `test_composition_views_support_compound_vowels_and_finals` | 단위 | PASS |
| 6 | 공백으로 나뉜 자모를 임의로 합치지 않는다 | `test_composed_input_views_do_not_join_unrelated_or_separated_input` | 통합 | PASS |

## 알려진 범위

- ASCII 두벌식 연속 입력만 변환한다. 세벌식과 일반 로마자 표기 변환은 범위 밖이다.
- 자판·자모 변환 뒤의 공백/구분자 우회 view 조합은 아직 지원하지 않는다.
- 기존 두 실패를 제외한 전체 회귀 명령에서 `305 passed, 1 deselected`, branch coverage
  `95.58%`를 확인했다. 제외된 항목은 기존 `시이발` corpus 충돌과 깨진 TOML을 직접 읽는
  패키지 테스트다.
- 패키지 빌드는 기존 `pyproject.toml` 손상 복구 후 다시 실행해야 한다.
