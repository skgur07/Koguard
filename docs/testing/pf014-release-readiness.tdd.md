# PF-014 release readiness TDD 증거

## RED

`tests/test_hidden_evaluation_report.py`와 `tests/test_release_report.py`를 먼저 추가했다. 첫 실행은
`evaluation.hidden_evaluation_report`와 `release.release_report`가 존재하지 않아 collection에서
2개 import error로 실패했다.

## 구현 계약

- hidden protected ablation과 attestation을 SHA-256으로 결박
- corpus hash·건수, manifest version과 고정 누출 normalization 기록
- direct/normalized leak 0건과 unresolved review 0건 강제
- 독립 consensus, privacy·rights 완료와 서로 다른 두 역할 승인 강제
- 공개 hidden report에서 원문, case ID, canonical term과 reviewer ID 제거
- strict·balanced·aggressive 전체 집계와 balanced slice metrics만 출력
- artifact audit, rights, 최종 commit CI, 공개 계약, hidden, TestPyPI gate 통합
- 누락 evidence를 숨기지 않고 stable blocker code로 기록
- 모든 gate 통과 뒤에도 maintainer 승인 전에는 main/PyPI 상태를 false로 유지

## GREEN

구현 직후 targeted 13 tests가 통과했다. hash가 다른 corpus, leak 1건, 닫힌 계약 위반, 동일 승인자, hidden commit
불일치와 TestPyPI artifact hash 불일치를 각각 거부하거나 release blocker로 유지하는 것을
확인했다. 최종 정렬 후 전체 634 tests와 branch coverage 95.62%, format, lint, mypy,
dictionary provenance, build, artifact audit, wheel·sdist clean-install smoke가 모두 통과했다.

## 2026-08-19 최종 evidence hardening

전체 리뷰에서 schema상 필수인 profile·slice·limitation이 없는 축약 hidden JSON도 release gate를
통과하는 실패를 재현했다. 또한 artifact audit에 commit/tree가 없고 CI 상태를 CLI 인자로
직접 만들 수 있어 stale evidence를 최종 commit에 연결할 수 있었다.

RED 테스트는 다음을 먼저 고정했다.

- 축약·unknown-field·corpus 합계 불일치 hidden report 차단
- hidden 평가 wheel SHA-256과 artifact audit wheel 불일치 차단
- artifact audit release commit 불일치 거부
- closed CI evidence와 세 OS job 성공 강제
- GitHub Actions API 응답의 stale commit·누락 job 거부
- closed rights manifest와 artifact source identity 기록

구현 후 targeted 36 tests가 통과했다. `release.github_actions_evidence`는 실제 Actions run/job API를
조회해 증거를 만들고, `release.release_report` CLI는 같은 조회 경로를 직접 사용한다. hidden
attestation은 평가에 사용한 wheel SHA-256을 기록하며 최종 gate가 audited wheel과 대조한다.
최종 전체 gate 수치는 모든 후속 hardening이 끝난 release commit에서 다시 기록한다.
