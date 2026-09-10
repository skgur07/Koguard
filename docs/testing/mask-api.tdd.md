# 마스킹과 금칙어 보완 검증

2026-09-10 사용자 요청: 기존 속도·프로필을 유지하면서 마스킹 기능과 확인된 누락을 보완한다.
사용자 여정은 대화에서 정했다. 새 마스킹 API, 사용자 대체 문자, 원문·허용어 보존,
입력·계산량 제한, 누락 literal의 탐지와 마스킹을 검증한다.

## TDD 근거

- RED: `uv run --no-sync pytest tests/test_mask.py -q --no-cov` — 18 failed, 4 passed.
  mask 미구현과 새 literal 미탐지가 원인이다.
- GREEN: 같은 명령 — 22 passed.
- 공개 API inventory 검사는 새 메서드를 허용 목록에 반영한다. module-level mask는 추가하지 않는다.
- Git checkpoint commit은 만들지 않았다. 현재 작업 환경에서 `.git`은 읽기 전용이며,
  작업 diff와 이 보고서에 RED/GREEN 근거를 보존한다.

## 한계

추가 literal은 소유자가 승인한 단일 변형이며 독립 평가에서 승격한 자료가 아니다.
확정 tuning 2,763건 원문이 없어 전체 독립 정확도 재측정은 수행하지 않는다.
이전 후보의 hidden·CI·TestPyPI 근거를 변경된 배포물에 재사용하지 않는다.
후속 공개 전 새 후보 평가와 TestPyPI 검증이 필요하다.

## 최종 검증

- `uv sync --frozen --offline --all-extras --dev`: 최초에는 editables 캐시 누락으로 실패.
  네트워크를 허용한 `uv sync --frozen --all-extras --dev`로 잠금 의존성 설치 완료.
- ruff format/check, mypy 통과: 83개 포맷 검사, 82개 타입 검사 대상.
- 전체 pytest: 861 passed, branch 측정 포함 총 coverage 95.92%.
- 배포 smoke 보완 후 관련 release 테스트: 32 passed.
- provenance validator: 74 candidates, 4 sources, 68 literals, 5 aliases.
- wheel/sdist 빌드 및 두 배포물의 독립 환경 설치·마스킹 smoke 통과.
- 배포 payload 확인: 새 literal, sdist 마스킹 문서·테스트 포함. 캐시·annotation-work 제외.
- 공식 artifact audit는 tracked worktree가 깨끗하지 않아 실패. 우회하거나 이전 commit에
  새 배포물의 검증을 연결하지 않았다. 커밋된 새 RC에서 다시 수행해야 한다.
- TestPyPI/PyPI 업로드 및 원격 CI·hidden 재평가는 수행하지 않았다.

## 공개 진단·성능

기존 공개 진단 52건에서 strict/balanced/aggressive 모두 direct-12 한 건만 False → True.
나머지 51건은 Match 전체가 동일하다. 독립 gold 정확도 수치가 아니다.

`contains()`·`check()` 구현 경로는 수정하지 않았다. 초기 별도 실행 측정은 실행 시점의
편차가 커서 성능 동등성 근거로 쓰지 않는다. 동일 코드에서 이전 사전(새 literal 제외)과
현재 사전을 번갈아 비교했다. 엔진 재사용, 10회 warmup, 100회 측정, 순서를 교대한
5라운드 p95 중앙값 기준이다. 코드 경로 변경이 없으므로 사전 증가의 비용을 확인한다.

| 입력 | 이전 사전 p95 ms | 현재 사전 p95 ms |
| --- | ---: | ---: |
| balanced 짧은 정상 | 0.0429 | 0.0422 |
| balanced 짧은 욕설 | 0.0570 | 0.0537 |
| balanced 정상 4096자 | 9.4661 | 9.6672 |
| balanced 끝 욕설 4096자 | 11.2473 | 11.0845 |
| aggressive 짧은 정상 | 0.2047 | 0.2078 |
| aggressive 짧은 욕설 | 0.1979 | 0.1504 |
| aggressive 정상 4096자 | 16.4566 | 15.7294 |
| aggressive 끝 욕설 4096자 | 15.5172 | 17.8354 |

마지막 항목은 +14.9%여서 9라운드로 별도 재확인했다: 15.2417 → 14.8959ms (-2.3%).
일관된 속도 저하는 재현되지 않았지만 OS/CPU 변동이 크므로 정확한 성능 동등성이나
속도 향상을 주장하지 않는다. mask 자체는 탐지에 문자열 치환 비용을 추가한다.
원시 수치는 [mask-evidence](mask-evidence/)에 저장한다.

## 최종 자체 리뷰

추가 의존성·입력 로그 없음. 기본 설정, 예외 상한, 공개 Match 계약 유지.
정확성 4/5(전체 회귀 통과, 독립 corpus 재평가 미실행), 완결성 4/5(구현·로컬 배포 검증
완료, 원격 배포 gate 남음), 명확성 4/5(API 예제·문서 제공, 평가 기록은 유지관리자용),
실행 가능성 4/5(설치 가능한 로컬 배포물, 커밋된 RC 감사 필요), 간결성 4/5(런타임 19줄
추가, 추적 문서는 여러 파일에 걸침). 평균 4.0/5.
후속 우선순위는 새 RC 감사·독립 평가와 TestPyPI 설치 검증이다.
사용자도 구현 완료와 공개 배포 미완료의 구분에 동의할 수 있도록 완료 보고에 명시한다.
