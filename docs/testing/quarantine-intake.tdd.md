# Quarantine intake TDD 기록

## RED

`tests/test_quarantine_intake.py`를 먼저 추가하고 `evaluation.quarantine_intake`가 없는 상태에서
수집 모듈 import 실패를 확인했다. 테스트 계약은 고정 artifact 검증, Curse 중복과 민감 패턴
제외, deterministic 선택, 원문 없는 집계 report, 권리 대기 상태, CLI 비노출이다.

## GREEN

`evaluation/quarantine_intake.py`와 닫힌 version 1 source/report schema를 구현했다. 단위 테스트
7개가 통과했고, 실제 고정 ZIZUN artifact에서 500건 로컬 review queue를 재현했다.

## 회귀 방지

- dataset, LICENSE, provenance와 exclusion 원본은 SHA-256·byte size로 검증한다.
- upstream label은 선택 strata로만 쓰고 case에는 복사하지 않는다.
- 생성 case는 `review`, `LicenseRef-PendingReview`, `redistribution_allowed=false`로 고정한다.
- report와 CLI는 원문이나 canonical term을 출력하지 않는다.
- 로컬 queue는 Git과 sdist에서 제외한다.
