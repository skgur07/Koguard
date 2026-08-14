# PF-008 Profile API 계약 TDD 기록

## RED 범위

`tests/test_profile_contract.py`는 PF-009 구현 전에 다음 공개 동작을 고정한다.

- 세 profile의 모든 matcher flag와 `engine.config` 결과
- 인자 없는 engine의 `balanced` 기본값
- `aggressive`와 기존 all-enabled 설정의 동일성
- profile과 직접 config의 충돌 및 잘못된 profile 오류
- 모든 profile의 Exact+Alias core와 Whitelist 구간 계약
- profile별 우회 탐지 범위 차이
- 결정성과 하나의 engine을 공유하는 동시 호출 안전성
- 새 `*_matching` 설정이 profile에 자동 편입되지 않는 폐쇄 목록

아직 구현하지 않은 계약에는 `xfail(strict=True)`를 붙인다. 이 표시는 성공을 가장하지 않고
정상 전체 suite에서 예정된 실패만 격리한다. 다음 명령은 PF-008에서 통과해야 한다.

```powershell
uv run pytest --no-cov tests/test_profile_contract.py
```

실제 RED를 확인할 때는 `xfail` 처리를 해제해 실행한다. PF-009 전에는 이 명령이 실패해야 한다.

```powershell
uv run pytest --no-cov --runxfail tests/test_profile_contract.py
```

## GREEN

PF-009에서 `xfail` 표시를 제거하고 계약을 바꾸지 않은 채 profile 설정 factory와 생성자
해석을 구현했다. 집중 실행 결과는 29개 전부 통과다. `EngineConfig()`의 기존 all-enabled
동작은 유지하고 인자 없는 `KoguardEngine()`만 balanced로 전환했다.

기존 all-enabled 회귀 corpus와 PF-007 후보 평가는 `profile="aggressive"`를 명시해 기준선이
기본값 변경에 따라 조용히 바뀌지 않도록 했다. 공개 전 기대 matcher 표, 기본 profile 또는
오류 계약을 바꿀 때는 독립 평가 근거와 이 문서를 함께 갱신한다.
