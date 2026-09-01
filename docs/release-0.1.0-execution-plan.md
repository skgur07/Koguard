# Koguard `0.1.0` 출시 실행 계획

- 상태: **실행 중 — 480건 독립 판정 대기**
- 기준일: 2026-09-01
- 기준 브랜치: `dev`
- 계획 시작 기능 commit: `bb919046a455b09f75cb69c720b9753973dcf150`
- 추적 이슈: [PF-005 #7](https://github.com/skgur07/Koguard/issues/7),
  [PF-014 #16](https://github.com/skgur07/Koguard/issues/16)

이 문서는 `0.1.0` 공개까지의 **단일 실행 현황판**이다. 장기 방향과 정책 근거는
[제품 집중 계획](product-focus-plan.md)에 보존하되, 지금 무엇을 하고 있고 다음에 무엇을 할지는
이 문서에서만 관리한다.

## 1. 이번 출시의 종료점

`0.1.0`은 다음 범위의 가벼운 규칙 기반 Python 라이브러리로 공개한다.

- 사전·Alias와 승인된 표기 변형을 문맥과 무관하게 탐지
- `strict`, `balanced`, `aggressive` profile 제공
- 원문 match 구간과 결정적인 결과 순서 보장
- 겹치는 구간만 보호하는 사용자 Whitelist 제공
- 런타임 네트워크·외부 모델·필수 제3자 의존성 없음

이번 출시에서는 Adapter, Plugin, AI/Embedding, 다국어 필터, 새 외부 corpus, 새 matcher 계열을
추가하지 않는다. 이 항목은 `0.1.0` 공개 후 별도 근거와 이슈가 있을 때만 재개한다.

## 2. 범위 고정 규칙

아래 규칙으로 평가 작업이 다시 끝없이 늘어나는 것을 막는다.

1. 현재 생성한 positive 변형·decoy 480건 외에 새 tuning corpus를 만들지 않는다.
2. 사용자가 확정한 문맥 무관 lexical 정책과 재현 사례를 이번 탐지 수정의 근거로 사용한다.
3. 수정 대상은 현재 확인된 `공백/혼합 우회 + 한국어 조사 경계`로 제한하고, 480건
   독립 판정은 수정 후 별도 검증으로 사용한다.
4. 수정 중 다른 문제를 발견해도 보안·데이터 손상·공개 API 파손이 아니면 후속 이슈로 넘긴다.
5. hidden evaluation은 최종 품질 확인에만 사용하며 결과를 보고 규칙을 다시 튜닝하지 않는다.
6. 모든 자동 gate가 통과해도 `main` 병합, tag, TestPyPI/PyPI 게시는 소유자의 명시적 승인 뒤에
   실행한다.

## 3. 현재까지 완료된 상태

| 영역 | 상태 | 현재 근거 |
| --- | --- | --- |
| Core API | 완료 | `check()`, `contains()`, match span, Whitelist |
| 공개 profile | 완료 | `strict`, 기본 `balanced`, 선택 `aggressive` |
| 기본 데이터 provenance | 완료 | packaged term 67개, Alias 5개, 미확인 항목 0개 |
| tuning 기준선 | 완료 | 확정 2,763건: positive 639, hard-negative 2,124 |
| positive 변형 입력 | 생성 완료 | 8개 slice, positive-target 240 + decoy 240 |
| positive 변형 판정 | 대기 | 전 항목 `review`, `gold_ready=false` |
| 패키징·CI | 완료 | [751 tests, coverage 95.58%, 3 OS·재현성 gate 통과](https://github.com/skgur07/Koguard/actions/runs/33470014209) |
| 배포물 격리 | 완료 | tuning 자료는 wheel/sdist에 포함되지 않음 |
| 최종 hidden 평가 | 대기 | 확정 release candidate에서 1회 실행 |
| TestPyPI·공개 | 대기 | 최종 artifact와 소유자 승인 필요 |

경계 수정 전 비-gold 진단은 `balanced` 63/240, `aggressive` 180/240, decoy 탐지 0/240이었다.
R1 수정 후 `balanced`는 63/240으로 유지되고 `aggressive`는 240/240으로 늘었으며 decoy 탐지는
계속 0/240이다. 이 수치는 480건의 독립 판정 전이므로 제품 정확도나 공개 성능으로 사용하지
않는다. 기존 tuning 2,763건에서는 strict·balanced 결과와 FP가 유지됐고 aggressive만 문장·
occurrence TP가 각각 1건 늘었다.

## 4. 실행 순서와 체크리스트

### R1. 조사 경계 탐지 보강

`시  발은`, `ㅅ ㅂ이`처럼 공백·혼합 우회 뒤에 한국어 조사가 붙는 미탐을 먼저
수정한다. 문맥과 무관하게 등록 표현의 substring을 차단한다는 공개 정책이 이미 확정됐으므로
480건 전체 판정을 기다리지 않는다.

- [x] `시  발은`, `ㅅ ㅂ이`와 혼합 separator 사례를 실패 테스트로 고정
- [x] 공백·혼합 우회 뒤 한글 조사가 붙는 경우 탐지
- [x] 원문 span과 canonical term이 기존 계약을 유지하는지 검증
- [x] 정상 decoy와 기존 hard-negative의 FP 증분 검증
- [x] 최대 입력 길이와 representative benchmark 회귀 검증
- [x] `strict`·`balanced`·`aggressive` 이동 규칙 검증
- [x] 변경 근거와 알려진 한계를 문서화

완료 조건:

- 확정된 재현 사례의 탐지가 회복된다.
- 문장 단위와 occurrence 단위 FP 예산을 넘지 않는다.
- 공개 API, 결정적 match 순서, 원문 index mapping에 회귀가 없다.

### R2. 480건 독립 판정과 수정 결과 검증

목적은 생성 의도와 detector 예측을 보지 않고 실제 정책 label과 match span을 확정하고, R1의
수정 결과를 독립 표본에서 검증하는 것이다.

- [x] 프로젝트 작성 480건 생성
- [x] 기존 corpus와 direct/NFKC+casefold 중복 0건 검증
- [x] primary·secondary·adjudicator 보호 작업본 생성
- [ ] primary가 480건을 독립 판정
- [ ] secondary가 같은 480건을 독립 판정
- [ ] 두 판정의 불일치만 adjudicator가 재심
- [ ] 미해결 `review`를 0건으로 만들거나, 합의 불가능 사례를 평가 대상에서 명시적으로 제외
- [ ] 확정본 validator와 privacy 검사를 통과
- [ ] R1 전후의 profile·slice별 변화를 aggregate로 비교
- [ ] aggregate만 저장소와 #7에 기록하고 원문별 판정·reviewer 정보는 공개하지 않음

완료 조건:

- 모든 평가 대상이 독립 합의 또는 재심 근거를 가진다.
- 확정 positive·hard-negative 수, slice별 수와 제외 건수가 aggregate 보고서에 기록된다.
- detector 출력은 판정 입력이나 정답으로 사용되지 않는다.
- R1 전후 결과가 현재 경계 수정의 실제 recall·FP 영향을 설명한다.

### R3. 최종 품질 평가와 release candidate 고정

- [ ] 공개 regression·tuning 전체 평가 실행
- [ ] 최종 `strict`·`balanced`·`aggressive` 전체 및 slice별 지표 기록
- [ ] hidden corpus와 direct/normalized 누출 0건 확인
- [ ] 고정 commit·wheel로 hidden evaluation 1회 실행
- [ ] case-level hidden 결과는 보호 환경에 유지하고 aggregate만 반출
- [ ] README의 지원 범위·성능·한계가 실제 결과와 일치하는지 검토
- [ ] 최종 release candidate commit 고정

완료 조건:

- unresolved hidden review와 split 누출이 0건이다.
- `balanced`의 합의된 정확도·FP 예산을 통과하거나, 실패 시 공개를 차단하고 원인을 기록한다.
- hidden 결과를 본 뒤 같은 release candidate를 다시 튜닝하지 않는다.

### R4. 패키지 검증과 공개 승인

- [ ] `uv run ruff format --check .`
- [ ] `uv run ruff check .`
- [ ] `uv run mypy`
- [ ] `uv run pytest`
- [ ] `uv build`
- [ ] provenance와 wheel/sdist artifact audit 통과
- [ ] wheel·sdist clean-install smoke 통과
- [ ] 최종 commit의 Windows·Ubuntu·macOS CI와 byte reproducibility 통과
- [ ] TestPyPI에 동일 artifact 업로드 후 CPython 3.11.9 설치·quickstart 검증
- [ ] 권리 manifest, MIT, NOTICE, changelog, 공개 API, 보안 신고 경로 최종 확인
- [ ] PF-005 #7 완료 조건 확인 후 종료
- [ ] PF-014 #16에 최종 release report 기록
- [ ] 소유자에게 `dev → main`, tag `v0.1.0`, PyPI 게시 승인 요청
- [ ] 승인 후에만 `main` 승격·tag·PyPI 게시

완료 조건:

- release report의 blocker가 0개이고 판정이 `ready-for-maintainer-approval`이다.
- TestPyPI evidence의 artifact hash가 최종 audit와 일치한다.
- 소유자 승인 후 PyPI `koguard==0.1.0` 설치와 quickstart가 재현된다.

## 5. 단계별 산출물

| 단계 | 저장소에 남길 것 | 공개하지 않을 것 |
| --- | --- | --- |
| R1 | aggregate 판정 보고서, 정책·validator 변경 | case별 reviewer, 보호 annotation 원문 |
| R2 | 실패 테스트, 최소 구현, 정확도·성능 회귀 | 임시 debug 출력, 실제 사용자 원문 |
| R3 | aggregate 성능, limitation, corpus·artifact hash | hidden 원문·case ID·canonical 정답 |
| R4 | release report, artifact hash, changelog | token·credential·보호 환경 경로 |

## 6. 진행 상태 갱신 방법

각 작업 묶음을 `dev`에 반영할 때 이 문서도 같은 commit에서 갱신한다.

1. 해당 체크박스를 완료로 바꾼다.
2. 상단의 상태·기준일·기준 commit을 갱신한다.
3. 검사 건수, coverage, CI URL처럼 다시 실행한 증거만 최신 값으로 바꾼다.
4. 새 blocker는 아래 표에 한 줄로 추가하고 해결되면 삭제하지 말고 `해결`로 남긴다.
5. #7에는 corpus·판정 진행만, #16에는 release gate 진행만 aggregate로 기록한다.

## 7. blocker 기록

| ID | 상태 | 내용 | 해제 조건 |
| --- | --- | --- | --- |
| B-01 | 해결 | 공백/혼합 우회 뒤 조사 경계 미탐 후보 60건 | R1 정확도·회귀 gate 통과 |
| B-02 | 열림 | positive 변형 480건이 아직 미판정 | R2 독립 합의·재심 완료 |
| B-03 | 열림 | 최종 hidden aggregate 없음 | R3 보호 평가·attestation 완료 |
| B-04 | 열림 | TestPyPI 동일 artifact 설치 증거 없음 | R4 TestPyPI smoke 완료 |
| B-05 | 열림 | `main`·PyPI 공개 승인 전 | B-01~04 해제 후 소유자 명시 승인 |

## 8. `0.1.0` 이후로 넘긴 작업

다음 항목은 이번 계획의 완료 조건이 아니다.

- Adapter와 웹 프레임워크 통합
- Plugin manager
- AI/Embedding 기반 의미적 모욕 탐지
- 다국어 욕설과 세벌식 자판 변환
- 무제한 leetspeak·동형 문자·이모지 대체
- 새로운 외부 corpus 수집과 대규모 사전 확장
- 문맥에 따라 core 탐지를 해제하는 모델

공개 후 실제 false-negative·false-positive 제보와 사용 수요를 기준으로 `0.2.0` backlog를 새로
우선순위화한다.
