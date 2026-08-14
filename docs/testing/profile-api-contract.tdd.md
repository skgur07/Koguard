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

PF-009 완료 시 `xfail` 표시를 제거하고 두 번째 명령까지 통과시킨다. 구현 편의를 위해 기대
matcher 표, 기본 profile, 오류 계약을 완화하지 않는다.
