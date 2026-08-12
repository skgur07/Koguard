# Corpus split·접근 정책

이 문서는 PF-004가 고정한 tuning, hidden evaluation, private service corpus의 운영 경계다.
기계 검증 계약은 `evaluation/split-manifest.schema.json`, 실행 도구는
`evaluation/split_guard.py`, 현재 공개 assignment는
공개 regression의 기본 manifest는 `evaluation/splits/corpus-splits.v1.json`이다. PF-005의
로컬 review intake ID를 포함한 v2는 비민감 aggregate 근거로 보존하되 원문과 함께 검증할 때만
명시적으로 선택한다.

## 역할과 열람 경계

| 역할 | regression | tuning | hidden evaluation | private service |
| --- | --- | --- | --- | --- |
| 규칙·사전 작성자 | 원문 | 원문 | 원문 열람 금지, aggregate report만 | 원문 열람 금지 |
| corpus custodian | 원문 | 원문 | 보호 환경에서 원문 | 승인된 비식별 원문 |
| release reviewer | 원문 | 원문 | aggregate와 manifest | aggregate만 |

한 사람이 여러 역할을 맡더라도 릴리스 단위로 역할을 선언한다. hidden evaluation 원문을 본
사람은 같은 version을 대상으로 사전, matcher, threshold를 조정하지 않는다. 불가피하게 원문이
노출되면 해당 version은 hidden 자격을 잃고 tuning으로 이동하며 새 evaluation version을 만든다.

## Stable-ID manifest

- case ID는 원문, 사용자명이나 내부 서비스 식별자를 포함하지 않는 불투명하고 안정적인 값이다.
- 모든 materialized case는 manifest의 `case_id`, `corpus_id`, `split`과 정확히 일치해야 한다.
- assignment 또는 누출 정규화 계약 변경에는 `manifest_version` 증가와 구체적인
  `change_reason`이 필요하다.
- 이전 manifest와 aggregate report는 삭제하거나 덮어쓰지 않고 릴리스 근거로 보존한다.
- hidden manifest는 stable ID만 공유할 수 있고 원문, canonical term, 재식별 가능한 경로는
  공개 artifact에 포함하지 않는다.

변경은 corpus custodian과 release reviewer가 각각 데이터 경계와 품질 영향을 확인한 뒤 두 명이
승인한다. 긴급 수정도 version과 사유를 생략할 수 없다. 규칙 작성자는 hidden case 추가·제거
목록을 직접 선택하지 않고 필요한 slice와 목표 건수만 요청한다.

## 누출 검사

보호 환경에서 regression, tuning, hidden evaluation을 한 번에 guard에 전달한다. guard는 다음
두 fingerprint를 실행 중 메모리에서만 계산하며 report나 manifest에 원문 hash를 저장하지 않는다.

1. UTF-8 원문 SHA-256
2. NFKC, casefold, Unicode 구두점·separator·format 제거, 연속 반복 축약 뒤 SHA-256

hidden evaluation과 공개 regression/tuning 사이에서 하나라도 겹치면 실패한다. 보수적
정규화로 인한 충돌은 자동 허용하지 않고 custodian이 두 case를 확인해 한 split에서 제외한다.
오류에는 case ID와 split만 남고 원문과 canonical term은 출력하지 않는다.

## 저장과 공개 artifact 경계

- hidden evaluation과 private 원문은 공개 Git 저장소, fork, PR, issue, CI artifact와 일반
  개발자 workstation에 복사하지 않는다.
- 보호 원문은 접근 로그와 저장 시 암호화를 제공하는 제한된 저장소에 둔다.
- repository root 아래 `evaluation/hidden`, `evaluation/private`, `evaluation/protected`는
  방어적으로 ignore하며, guard는 경로가 repository 안이면 ignore 여부와 무관하게 실패한다.
- 공개 sdist에는 schema, guard, 공개 manifest, source pin과 작은 regression corpus만 포함한다.
  2,500건 tuning review intake 원문은 수동 privacy review 전까지 Git과 sdist에서 제외하고
  로컬 보호 artifact로만 유지한다. wheel에는 모든 평가 도구와 corpus를 포함하지 않는다.
- aggregate report도 case ID가 서비스 사용자와 연결될 수 있으면 공개하지 않는다.

## Private service 개인정보·보존

수집 전에 서비스 정책과 적법한 처리 근거를 확인한다. 계정 ID, 닉네임, URL token, 연락처,
세션·기기 식별자와 주변 대화를 제거하고 탐지 판정에 필요한 최소 문맥만 남긴다. 비식별화로
표현 의미나 span이 달라지면 수정본을 사용하지 않고 case를 폐기한다.

- 접근은 corpus custodian 중 작업에 필요한 사람에게만 기간을 정해 부여한다.
- 원본 서비스 추출물은 annotation 및 품질 확인이 끝나면 즉시 삭제하며 30일을 넘기지 않는다.
- 비식별 private annotation은 180일마다 필요성을 재승인하고, 승인되지 않으면 삭제한다.
- 접근·반출·삭제 기록은 원문 없이 actor, 시각, 목적, corpus version만 남긴다.
- 삭제 요청이나 보안 사고가 발생하면 정상 주기를 기다리지 않고 관련 version을 격리·삭제하고
  manifest와 공개되지 않은 aggregate report의 유효성을 재검토한다.

## 릴리스 실행 절차

1. 규칙 작성자는 tuning 결과로 변경을 완료하고 commit을 고정한다.
2. corpus custodian은 보호 환경에서 고정 commit과 hidden version을 선택한다.
3. 이전 manifest를 지정해 split guard를 실행하고 누출 0건을 확인한다.
4. 동일 환경에서 evaluation runner를 실행한다. 원문이 없는 aggregate report만 전달한다.
5. release reviewer는 manifest version, corpus hash, 환경, 전체·slice별 `n`과 지표를 확인한다.
6. 실패 cluster는 원문 대신 slice와 건수로 tuning 작업에 전달한다. 원문 검토가 필요하면 기존
   hidden version을 폐기한 뒤 해당 case를 tuning으로 이동한다.
