# PF-004 corpus split guard TDD 기록

## RED

`tests/test_split_guard.py`에 stable-ID manifest, 원문·정규화 누출, protected 경로, version 변경,
비민감 CLI 출력 계약을 먼저 작성했다. 구현 전에는 `evaluation.split_guard` 모듈이 없어 테스트
수집이 실패했다.

## GREEN

표준 라이브러리만 사용하는 `evaluation/split_guard.py`와 closed JSON schema version 1을
추가했다. 현재 공개 regression 20건을 stable ID manifest에 고정하고 actual corpus의
`corpus_id`·split과 양방향으로 대조한다.

누출 검사는 원문 SHA-256과 NFKC·casefold·구두점/공백/format 제거·연속 반복 축약 fingerprint를
메모리에서 계산한다. 공개 regression/tuning과 hidden evaluation이 겹치거나 hidden/private
원문이 repository root 안에 있으면 case ID만 포함한 오류로 실패한다.

## 운영 경계

`docs/corpus-split-policy.md`에 규칙 작성자와 custodian 분리, hidden 변경의 두 명 승인,
manifest version/change reason, private 비식별화·최소권한·보존·삭제 정책을 기록했다. 공개
sdist에는 guard 계약만, runtime wheel에는 평가 파일을 포함하지 않는 기존 경계를 유지한다.
