# PF-014 `0.1.0` 릴리즈 준비 보고서

- 기준일: 2026-09-04
- 대상: Koguard `0.1.0`
- 현재 판정: **blocked — hidden evaluation·최종 RC CI 통과, TestPyPI 대기**
- 공개 상태: `main` 미승격, PyPI 미게시

## 완료된 선행 근거

PF-013은 `dev` merge commit `a93e2b1512afb3f659d0471fcb28def786bcc520`에서 완료했다.
GitHub Actions run `32115372635`의 Windows, Ubuntu, macOS CPython 3.11.9 job은 format, lint,
mypy, 621 tests, branch coverage 95.62%, dictionary provenance, build, artifact audit,
clean-install smoke와 artifact upload를 모두 통과했다. 프로젝트와 직접 작성한 기본 데이터는
MIT로 승인했고, 외부 자료의 revision·권리·포함/제외 범위는 rights manifest에 기록했다.

GitHub private vulnerability reporting은 2026-08-19 활성화했고 PF-013 이슈 #15는
`completed`로 종료했다. 이 CI와 commit은 PF-014 도구를 추가하기 전의 선행 근거다. 최종
release commit이 정해지면 같은 3 OS gate를 다시 통과해야 한다.

PF-014 준비 변경은 Windows CPython 3.11.9에서 format, lint, mypy, 634 tests,
branch coverage 95.62%, dictionary provenance, wheel·sdist build, artifact audit과 두 산출물의
clean-install smoke를 통과했다. 이 결과는 로컬 준비 근거이며 최종 release commit의
3 OS GitHub Actions와 hidden·TestPyPI 근거를 대체하지 않는다.

## 역할과 hidden 원문 경계

현재 저장소 작업자는 규칙 작성자와 release reviewer 역할만 수행한다. hidden 원문은 열람하지
않고 aggregate와 manifest만 검토한다. corpus custodian은 저장소 밖의 접근 통제·암호화된 보호
환경에서 다음 순서로 실행한다.

1. 최종 release commit과 hidden corpus version을 고정한다.
2. 공개 regression·tuning과 hidden corpus를 split guard에 함께 전달해 direct/normalized 누출
   0건을 확인한다.
3. 같은 commit과 CPython 3.11.9에서 `evaluation.ablation_runner`를 실행하고 case-level report는
   보호 환경 밖으로 반출하지 않는다.
4. artifact audit의 wheel을 설치해 실행하고 해당 wheel SHA-256을 기록한다.
5. protected report SHA-256, corpus SHA-256·건수, manifest version, 독립 합의, privacy·rights
   완료와 서로 다른 custodian/release reviewer approval ID를 attestation에 기록한다.
6. `evaluation.hidden_evaluation_report`로 aggregate-only report를 생성해 전달한다.

hidden report 생성기는 다음 조건을 모두 강제한다.

- attestation과 protected ablation SHA-256 일치
- attestation의 evaluated wheel SHA-256과 최종 artifact audit 일치
- corpus SHA-256과 positive·hard-negative·review 건수 일치
- 확정 positive와 hard-negative 각각 1건 이상, unresolved review 0건
- 고정 split normalization version과 direct/normalized leak 0건
- `independent-consensus`, privacy review, rights review 완료
- corpus custodian과 release reviewer approval ID 분리
- 출력에서 case ID, 원문, canonical term과 reviewer ID 제거

## PF-014 release report

`release.release_report`는 다음 증거를 하나의 결정 보고서로 묶는다.

- `release.artifact_audit`의 release commit·Git tree, wheel·sdist metadata, 크기와 SHA-256
- closed MIT rights manifest와 공개 payload 승인 상태
- GitHub API에서 직접 확인한 최종 release commit의 3 OS CI와 reproducibility 승격 job 성공
- 공개 API 동결, README 주장 검토, 알려진 한계, core/AI 범위 분리
- `gold_ready=true` hidden aggregate와 balanced gate
- TestPyPI의 동일 artifact hash 설치 및 smoke evidence

```powershell
uv run python -m release.release_report `
  --artifact-audit C:\handoff\release-audit.json `
  --release-commit <40-character-final-commit> `
  --ci-run-url <final-ci-run-url> `
  --public-contract-reviewed `
  --private-vulnerability-reporting-enabled `
  --hidden-evaluation C:\handoff\pf014-hidden-v1.aggregate.json `
  --testpypi-evidence C:\handoff\testpypi-evidence.json `
  --output C:\handoff\release-report.json
```

`--ci-run-url`은 성공으로 간주하는 수동 문자열이 아니다. release report CLI가 GitHub Actions
run과 jobs API를 다시 조회해 repository, workflow, head SHA, trigger, conclusion과 정확한 세 OS
CPython 3.11.9 job을 확인하고 canonical CI evidence hash를 최종 보고서에 기록한다. API rate
limit이 필요한 환경에서는 `GITHUB_TOKEN`을 설정할 수 있으며 값은 보고서나 로그에 남기지 않는다.

artifact audit CLI는 clean Git checkout에서 `HEAD`와 `HEAD^{tree}`를 직접 읽는다. 따라서
commit되지 않은 tracked 변경으로 만든 산출물은 release evidence로 감사할 수 없다.

hidden 또는 TestPyPI evidence가 없으면 보고서는 실패로 사라지지 않고 `decision=blocked`와
구체적인 blocker code를 기록한다. 모든 자동 gate가 통과해도 결과는
`ready-for-maintainer-approval`이며 `main_promoted=false`, `pypi_published=false`를 유지한다.
실제 `dev → main`, tag와 PyPI 업로드는 별도 명시적 승인 없이는 실행하지 않는다.

## 2026-09-04 독립 hidden evaluation

release candidate `813fc36c6988a7bdab68027964a206e970ab9f52`에서 Linux CI가 만든 wheel
SHA-256 `0dd69e7aca1319694fb879ed86be7e4d79ac95d9ff539216416683c6d9a4546e`을 CPython
3.11.9 보호 환경에 설치해 hidden evaluation을 정확히 한 번 실행했다. 새 출처 K-HATERS의
고정 test artifact 10,000건에서 stable SHA-256 층화로 600건을 뽑은 뒤 공개 자료 direct 중복
1건과 용량 조정 99건을 제외했다. 독립 primary·secondary 판정과 제3 재심 후 `review` 76건은
label을 강제하지 않고 제외해 positive 16건, hard-negative 408건, 총 424건을 최종 평가했다.

공개 regression 20건·tuning 3,980건·hidden 424건을 manifest version 2로 함께 검사한 결과
direct/normalized leak은 모두 0건이다. case-level 원문·ID·canonical term·reviewer ID는 보호
환경에만 남겼고, 공개 가능한 결과는
`evaluation/results/pf014-hidden-khaters-v1.aggregate.json` 하나뿐이다.

이 aggregate와 문서를 기록한 후속 commit은 측정 증거 보존용이며 새 release candidate가 아니다.
README metadata가 달라져 후속 commit에서 다시 만든 wheel·sdist hash는 바뀌므로 TestPyPI에는
반드시 hidden 평가와 artifact audit에 결박된 `813fc36`의 wheel·sdist를 그대로 사용한다.

| profile | 문장 TP/FP/FN/TN | 문장 precision/recall/F1 | occurrence TP/FP/FN |
| --- | --- | --- | --- |
| strict | 12/0/4/408 | 100% / 75.0% / 85.7% | 13/0/5 |
| balanced | 14/0/2/408 | 100% / 87.5% / 93.3% | 15/0/3 |
| aggressive | 16/6/0/402 | 72.7% / 100% / 84.2% | 18/7/0 |

balanced는 strict 대비 문장 TP +2·FP +0, occurrence TP +2·FP +0이다. 정상 문장 FP rate
0%, short chat p95 0.0646ms, 최대 4,096자 p95 8.9211ms로 합의된 정확도·성능 gate를 모두
통과했다. tuning의 occurrence FP +2는 독립 hidden에서 재현되지 않았지만 없던 사실로 지우지
않고 tuning 한계로 함께 공개한다. 이 결과를 본 뒤 matcher·사전·profile은 변경하지 않았다.

## TestPyPI evidence 계약

TestPyPI 업로드는 이번 준비 변경에 포함하지 않는다. trusted publisher 또는 제한된 API token을
설정한 뒤 최종 wheel과 sdist를 업로드하고, CPython 3.11.9의 새 환경에서 각각 설치한다.
`release/testpypi-evidence.schema.json`에는 다음만 기록한다.

- 고정 TestPyPI index와 project URL
- package `koguard==0.1.0`
- Python `3.11.9`
- metadata 표시 검증 완료
- wheel·sdist의 artifact audit와 동일한 SHA-256
- 각 artifact clean-install quickstart 성공

## 현재 blocker와 다음 실행

| gate | 상태 | 다음 작업 |
| --- | --- | --- |
| PF-013 CI·license·artifact | 완료 | RC `813fc36`, Actions `33581853944` 통과 |
| 비공개 취약점 신고 | 완료 | 릴리스 후 정책 유지 |
| hidden evaluation | 완료 | 424건 독립 평가, 누출 0건, balanced gate 통과 |
| TestPyPI | 대기 | 게시 권한 설정 후 동일 artifact 설치 smoke |
| `main`·PyPI 승인 | 대기 | 모든 evidence 확인 후 소유자 명시 승인 |

현재 tuning 2,763건에서 balanced는 strict보다 occurrence FP가 2건 늘어 tuning 전체 gate를
통과하지 못했다. 반면 독립 hidden 424건에서는 문장·occurrence FP 증분이 모두 0이라 hidden
release gate를 통과했다. 두 분포의 차이를 숨기지 않으며, 16개 positive뿐인 hidden 표본을 모든
실서비스 정확도로 일반화하지 않는다.

## 2026-09-02 R3 재측정

최종 tuning 2,763건을 100회 측정해 기존 결과를 재현했다. strict 문장 TP/FP/FN/TN은
416/0/223/2,124, balanced는 440/0/199/2,124, aggressive는 455/30/184/2,094다.
occurrence TP/FP/FN은 각각 554/37/420, 584/39/390, 589/96/385다. balanced 최대 입력
p95는 12.9194ms로 성능 예산을 통과했지만 strict 대비 occurrence FP +2로 전체 gate는 실패한다.

보호용 통합 split manifest로 regression 20건과 확정·targeted tuning 3,980건을 함께 검사해
direct/normalized leak 0건을 확인했다. hidden corpus가 없으므로 이 결과는 hidden 누출 0건을
대신하지 않으며, 최종 release candidate 고정과 hidden 1회 평가는 계속 차단한다.
