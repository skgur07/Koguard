# Koguard `0.1.0` 출시 실행 계획

- 상태: **차단 — 새 후보 `e657692` CI·artifact 통과, hidden 평가 대기**
- 기준일: 2026-09-09
- 기준 브랜치: `dev`
- 계획 시작 기능 commit: `bb919046a455b09f75cb69c720b9753973dcf150`
- 이전 고정 RC: `813fc36c6988a7bdab68027964a206e970ab9f52` (2026-09-08 기준 **대체 예정**)
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
7. 한 후보의 hidden aggregate를 기록한 뒤에는 그 후보를 다시 튜닝하거나 다시 패키징하지
   않는다. 새 후보가 필요하면 §3.1의 절차로 별도 후보를 만들고, TestPyPI와 실제 공개에는
   그 후보의 평가된 artifact hash만 사용한다. 이전 후보의 결과는 덮어쓰지 않는다.

## 3. 현재까지 완료된 상태

| 영역 | 상태 | 현재 근거 |
| --- | --- | --- |
| Core API | 완료 | `check()`, `contains()`, match span, Whitelist |
| 공개 profile | 완료 | `strict`, 기본 `balanced`, 선택 `aggressive` |
| 기본 데이터 provenance | 완료 | packaged term 67개, Alias 5개, 미확인 항목 0개 |
| tuning 기준선 | 완료 | 확정 2,763건: positive 639, hard-negative 2,124 |
| positive 변형 입력 | 생성 완료 | 8개 slice, positive-target 240 + decoy 240 |
| positive 변형 판정 | 완료 | 독립 합의 480건: positive 240, hard-negative 240, review·불일치 0 |
| 패키징·CI | 완료 | [760 tests, coverage 95.63%, 3 OS·재현성 gate 통과](https://github.com/skgur07/Koguard/actions/runs/33581853944) |
| 배포물 격리 | 완료 | tuning 자료는 wheel/sdist에 포함되지 않음 |
| 최종 hidden 평가 | 이전 후보 완료 | RC `813fc36`, 독립 424건, balanced 문장 TP/FP/FN `14/0/2`, gate 통과 |
| 출시 후보 선택 | 확정 | 새 RC로 전환 — §3.1 |
| 새 후보 근거 | 미착수 | 품질 검사·hidden·CI·artifact 증거 필요 |
| TestPyPI·공개 | 대기 | 새 후보 artifact와 소유자 승인 필요 |

두 독립 reviewer는 설계 의도와 detector 출력 없이 480건 전부에 합의했다. 확정 label은
positive 240건, hard-negative 240건이며 review·불일치·privacy 제외는 0건이다. 같은 고정
표본의 문장 기준으로 R1 전 `strict/balanced/aggressive` TP는 `63/63/180`, FP는 모두 0이었고,
R1 후에는 `63/63/240`, FP 0으로 바뀌었다. 회복된 60건은 Whitespace 30건과 Mixed-gap 30건이다.
R1 후 aggressive occurrence도 TP/FP/FN `240/0/0`이다. 최초 집계의 Alias 12건 canonical
불일치는 두 reviewer가 승인된 Alias 매핑으로 독립 재감사해 같은 12건을 교정했고, 원문 span과
label 오류는 0건이었다. 이 표본은 독립 tuning
근거이지만 프로젝트 작성 targeted corpus이며 `gold_ready=false`라 실서비스 전체 성능으로
일반화하지 않는다. 기존 tuning 2,763건에서는 strict·balanced 결과와 FP가 유지됐고
aggressive만 문장·occurrence TP가 각각 1건 늘었다.

### 3.1 출시 후보 결정 (2026-09-08)

**결정: 이전 고정 RC `813fc36`을 게시하지 않고, 이후 수정을 담은 새 release candidate를
만든다.** 근거는 [2026-09-08 검토 피드백](project-review-2026-09-08.md)의 F-05다.

`813fc36` 이후 `src/koguard`에 들어간 변경은 다음과 같다.

| commit | 내용 | 이전 RC 포함 여부 |
| --- | --- | --- |
| `110faa3` | matcher·normalizer 정규화·공백 매칭 최적화 | 미포함 |
| `ade45f2` | 기본 Whitelist 16개로 정상 용법 오탐 제거 | 미포함 |
| 2026-09-08 검토 수정 | F-01 반복 축약 선형화, F-02 사전 collection 검증, F-03 보호된 Alias 뒤 짧은 후보 재평가, F-04 공개 예외 계약 | 미포함 |

현재 README는 이 중 새 Whitelist 동작을 이미 설명하므로, 이전 RC를 게시하면 문서와 배포물이
어긋난다. F-03은 탐지 결과를, F-02·F-04는 공개 예외 계약을 바꾸므로 배포 후 수정이 아니라
후보 단계에서 포함해야 한다.

이전 후보의 근거 처리 원칙:

- `813fc36`의 hidden aggregate, attestation, CI 기록, artifact hash는 **그 후보의 역사적
  근거로 그대로 보존한다.** 새 후보의 결과로 덮어쓰거나 대체하지 않는다.
- 새 후보의 hidden 처리는 기존 [split 정책](corpus-split-policy.md)을 그대로 따른다. hidden은
  최종 확인에만 1회 사용하고, 결과를 보고 같은 후보를 다시 튜닝하지 않는다.
- 이전 후보의 aggregate를 새 후보의 기능·정확도·성능 근거로 인용하지 않는다.

### 3.2 새 후보 `e657692`의 확정 근거 (2026-09-09)

R5의 CI와 artifact 검증을 통과했다. 아래 값이 게시 대상이다.

| 항목 | 값 |
| --- | --- |
| commit | `e6576925cfce46ed0c23356d4610be3a5b0cebbe` |
| CI run | [`34191885636`](https://github.com/skgur07/Koguard/actions/runs/34191885636) |
| wheel sha256 | `61bd9c35a722b6e5c2cf94f1d17ed9e500205a99dae2f27d066841488152a658` |
| sdist sha256 | `fea513b21000060c91afa3133b3b4c0912fea65e7d388842c56275fa717a383a` |
| authoritative artifact | `koguard-0.1.0-release-candidate` (id `10042510763`) |

artifact 내부 경로는 `candidates/koguard-0.1.0-candidate-Linux-python311/dist/`로 게시
workflow가 기대하는 형태와 같다.

로컬 Windows 빌드의 hash는 이 값과 다르다. sdist 멤버 222개의 이름과 개수는 같고 텍스트
파일 29개만 크기가 다르며, 원인은 작업 복사본의 CRLF 줄바꿈이다. 릴리즈 판정에는 CI가 만든
artifact만 사용하고 로컬 빌드 hash를 근거로 쓰지 않는다.

**artifact 보존 기한:**

| artifact | 만료 |
| --- | --- |
| `koguard-0.1.0-release-candidate` | 2026-09-22 (실질 마감) |
| OS별 `koguard-0.1.0-candidate-*-python311` | 2026-09-11 |

이 기한을 넘기면 같은 commit이라도 CI를 다시 실행해 run-id와 artifact를 새로 고정해야 한다.

새 후보 확정 전 반드시 갱신해야 하는 고정값:

| 위치 | 현재 값 | 갱신 대상 |
| --- | --- | --- |
| [`publish-testpypi.yml`](../.github/workflows/publish-testpypi.yml) `RELEASE_COMMIT` | `813fc36c6988a7bdab68027964a206e970ab9f52` | 위 표의 commit |
| 같은 workflow `run-id` | `33581853944` | 위 표의 CI run |
| 같은 workflow `WHEEL_SHA256`·`SDIST_SHA256` | 이전 후보 hash | 위 표의 hash |

값은 확보했으나 아직 반영하지 않았다. hidden 평가를 통과하기 전에 반영하면 평가되지 않은
후보를 게시 가능한 상태로 두게 되므로, §2 규칙 7에 따라 hidden 완료 뒤에 갱신한다.
갱신 전에는 TestPyPI 게시 workflow를 실행하지 않는다.

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
- [x] primary가 480건을 독립 판정
- [x] secondary가 같은 480건을 독립 판정
- [x] 두 판정의 불일치만 adjudicator가 재심 — 불일치 0건으로 재심 대상 없음
- [x] 미해결 `review`를 0건으로 만들거나, 합의 불가능 사례를 평가 대상에서 명시적으로 제외
- [x] 확정본 validator와 privacy 검사를 통과
- [x] R1 전후의 profile·slice별 변화를 aggregate로 비교
- [x] aggregate만 저장소와 #7에 기록하고 원문별 판정·reviewer 정보는 공개하지 않음

완료 조건:

- 모든 평가 대상이 독립 합의 또는 재심 근거를 가진다.
- 확정 positive·hard-negative 수, slice별 수와 제외 건수가 aggregate 보고서에 기록된다.
- detector 출력은 판정 입력이나 정답으로 사용되지 않는다.
- R1 전후 결과가 현재 경계 수정의 실제 recall·FP 영향을 설명한다.

### R3. 최종 품질 평가와 release candidate 고정

- [x] 공개 regression·tuning 전체 평가 실행
- [x] 최종 `strict`·`balanced`·`aggressive` 전체 및 slice별 지표 기록
- [x] positive 변형 Alias canonical 불일치 12건 재감사와 release 영향 확정
- [x] hidden corpus와 direct/normalized 누출 0건 확인
- [x] 고정 commit·wheel로 hidden evaluation 1회 실행
- [x] case-level hidden 결과는 보호 환경에 유지하고 aggregate만 반출
- [x] README의 지원 범위·성능·한계가 실제 결과와 일치하는지 검토
- [x] 최종 release candidate commit 고정 — `813fc36c6988a7bdab68027964a206e970ab9f52`

R3의 결과는 `813fc36` 후보의 근거로 확정되어 있다. 2026-09-08 결정(§3.1)으로 이 후보는
게시하지 않으므로, 아래 완료 조건은 새 후보에 대해 R5에서 다시 충족해야 한다.

완료 조건:

- unresolved hidden review와 split 누출이 0건이다.
- `balanced`의 합의된 정확도·FP 예산을 통과하거나, 실패 시 공개를 차단하고 원인을 기록한다.
- hidden 결과를 본 뒤 같은 release candidate를 다시 튜닝하지 않는다.

### R4. 패키지 검증과 공개 승인

- [x] `uv run ruff format --check .`
- [x] `uv run ruff check .`
- [x] `uv run mypy`
- [x] `uv run pytest` — 761 passed, branch coverage 95.63%
- [x] `uv build`
- [x] provenance와 wheel/sdist artifact audit 통과
- [x] wheel·sdist clean-install smoke 통과
- [x] 최종 release candidate의 Windows·Ubuntu·macOS CI와 byte reproducibility 통과 — run `33581853944`
- [ ] TestPyPI에 동일 artifact 업로드 후 CPython 3.11.9 설치·quickstart 검증
- [x] 권리 manifest, MIT, NOTICE, changelog, 공개 API, 보안 신고 경로 최종 확인
- [ ] PF-005 #7 완료 조건 확인 후 종료
- [ ] PF-014 #16에 최종 release report 기록
- [ ] 소유자에게 `dev → main`, tag `v0.1.0`, PyPI 게시 승인 요청
- [ ] 승인 후에만 `main` 승격·tag·PyPI 게시

R4의 완료 표시도 `813fc36` 후보 기준이다. `uv build` 이하 패키지 검증과 CI 항목은 새 후보
commit에서 다시 실행해야 하며, 그 재실행은 R5에서 추적한다.

완료 조건:

- release report의 blocker가 0개이고 판정이 `ready-for-maintainer-approval`이다.
- TestPyPI evidence의 artifact hash가 최종 audit와 일치한다.
- 소유자 승인 후 PyPI `koguard==0.1.0` 설치와 quickstart가 재현된다.

### R5. 새 release candidate 준비 (2026-09-08 결정, §3.1)

- [x] 2026-09-08 검토 수정 F-01~F-04, F-06~F-07 구현과 회귀 테스트 추가
- [x] 수정 후 전체 로컬 품질 검사 통과 — 839 passed, branch coverage 95.88%
- [x] 공개 ablation corpus에서 이전 HEAD와 정확도 동일함을 확인
- [x] 새 후보 commit 고정과 3 OS·재현성 CI 통과 — `e6576925cfce46ed0c23356d4610be3a5b0cebbe`,
      run [`34191885636`](https://github.com/skgur07/Koguard/actions/runs/34191885636).
      Ubuntu·Windows·macOS CPython 3.11.9 각 839 passed, branch coverage 95.88%.
      재현성 판정 `builders=Linux,Windows,macOS`로 3 OS 빌드가 바이트 단위로 동일하다.
- [x] 새 후보 wheel/sdist artifact audit와 clean-install smoke 재실행 — audit 통과,
      wheel `61bd9c35a722b6e5c2cf94f1d17ed9e500205a99dae2f27d066841488152a658`,
      sdist `fea513b21000060c91afa3133b3b4c0912fea65e7d388842c56275fa717a383a`.
      wheel·sdist 각각 새 환경 설치와 quickstart를 통과했다.
- [ ] 새 후보로 hidden evaluation 1회 실행 (기존 split 정책, 이전 결과 보존)
- [ ] `publish-testpypi.yml`의 commit·run-id·artifact hash를 새 후보로 갱신

완료 조건:

- 새 후보의 근거가 이전 후보 근거와 분리되어 각각 남아 있다.
- TestPyPI와 PyPI에 올라갈 artifact hash가 새 후보의 audit 결과와 일치한다.

## 5. 단계별 산출물

| 단계 | 저장소에 남길 것 | 공개하지 않을 것 |
| --- | --- | --- |
| R1 | 실패 테스트, 최소 구현, 정확도·성능 회귀 | 임시 debug 출력, 실제 사용자 원문 |
| R2 | aggregate 판정·profile 보고서, 정책 상태 갱신 | case별 reviewer, 보호 annotation 원문 |
| R3 | aggregate 성능, limitation, corpus·artifact hash | hidden 원문·case ID·canonical 정답 |
| R4 | release report, artifact hash, changelog | token·credential·보호 환경 경로 |
| R5 | 새 후보 commit·CI run·artifact hash, 이전 후보와 분리된 aggregate | hidden 원문, 이전 후보 결과의 덮어쓰기 |

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
| B-02 | 해결 | positive 변형 480건이 아직 미판정 | R2 독립 합의 480건·불일치 0건으로 완료 |
| B-02A | 해결 | Alias slice 12건의 occurrence canonical 불일치 | 두 reviewer가 Alias 30건씩 재감사, 같은 12건 canonical 교정·span 오류 0건 확인 |
| B-03 | 해결 | 최종 hidden aggregate 없음 | 독립 424건 보호 평가·attestation·aggregate 완료 |
| B-03A | 해결 | tuning에서 balanced가 strict 대비 occurrence FP +2로 전체 gate 실패 | hidden에서 occurrence TP +2·FP +0 및 전체 gate 통과 |
| B-04 | 열림 | TestPyPI 동일 artifact 설치 증거 없음 | R4 TestPyPI smoke 완료 |
| B-06 | 열림 | 이전 RC `813fc36`에 `110faa3`·`ade45f2`와 2026-09-08 검토 수정이 빠져 있음 | R5 새 후보 확정·CI·hidden·artifact 증거 완료. commit·CI·artifact는 §3.2로 완료, hidden 평가만 남음 |
| B-07 | 열림 | `publish-testpypi.yml`이 이전 후보의 commit·run-id·hash를 고정 중 | 새 후보 값으로 갱신. 값은 §3.2에 확보했고 hidden 통과 후 반영 |
| B-08 | 열림 | authoritative artifact가 2026-09-22에 만료 | 그 전에 TestPyPI 게시, 또는 CI 재실행 후 run-id 재고정 |
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
