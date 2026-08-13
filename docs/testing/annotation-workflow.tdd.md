# PF-005 annotation workflow TDD 기록

## RED

구현 전에 blinded batch export, corpus SHA-256 고정, review-only 선택, 두 reviewer 합의 승격,
불일치·privacy 미승인 보존, 비민감 report와 CLI 출력 계약을 테스트했다.
`evaluation.annotation_workflow` 모듈이 없어 collection 단계에서 실패하는 것을 확인했다.

입력 corpus나 annotation batch를 출력 경로로 다시 지정했을 때 원본을 덮어쓰지 않아야 한다는
회귀 테스트도 추가했다. 보호 로직 전에는 두 테스트가 실제로 실패했다.

## GREEN

`annotation_workflow.py`는 stable ID 정렬로 최대 500건의 review batch를 export한다. batch에는
upstream label이나 detector prediction을 넣지 않으며, 서로 다른 reviewer ID의 두 결과가 모두
privacy 승인되고 label·span·canonical term·slice까지 일치할 때만 승격한다.

불일치, privacy pending과 exclude는 `review`로 유지한다. report는 label·slice·판정 품질 집계만
포함하고 원문, canonical term과 reviewer ID를 포함하지 않는다. 입력과 출력 경로가 겹치면 쓰기
전에 실패한다.

## 남은 운영 작업

도구와 계약은 실제 사람 판정을 대신하지 않는다. 2,500건에 대한 primary/secondary 판정과
adjudication, negative slice 보강, 출처 편향 완화와 hidden evaluation은 계속 별도 작업이다.

## 제3 판정 확장

RED 단계에서 최초 두 검토자의 불일치를 제3 검토자가 해결하는 함수가 없어 import 단계에서
실패함을 확인했다. 이어 서로 다른 세 reviewer 강제, 불일치 case의 완료 판정 강제, 명시적
`review` 유보, 비민감 CLI 집계를 계약 테스트로 고정했다.

GREEN 단계에서 `adjudicate` 명령을 추가했다. 최초 합의는 그대로 보존하고 불일치만 제3 판정으로
확정하며, privacy 제외와 unresolved는 별도 집계한다. 원문·canonical term·reviewer ID는 공개
report와 CLI 출력에 포함하지 않는다.
