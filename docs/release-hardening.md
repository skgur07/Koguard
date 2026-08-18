# PF-013 공개 hardening

- 기준일: 2026-08-18
- 대상: Koguard `0.1.0` release candidate
- 현재 상태: **MIT 승인·로컬 전체 gate 통과 — 원격 3 OS CI 검증 대기**

## 품질·패키징 계약

GitHub Actions는 Ubuntu, Windows, macOS와 CPython 3.11.9 조합에서 다음을 실행한다.

1. `uv sync --frozen --all-extras --dev`
2. Ruff format과 lint
3. mypy strict
4. pytest와 branch coverage 90% gate
5. packaged dictionary provenance 검증
6. wheel과 sdist build
7. artifact 내용·metadata·SHA-256·크기 감사
8. wheel과 sdist 각각의 격리 환경 clean-install quickstart

외부 GitHub Action은 이동 tag가 아니라 검토한 full commit SHA에 고정한다. CI 토큰 권한은
`contents: read`뿐이며 checkout credential을 보존하지 않는다. `uv`도 `0.12.3`으로 고정한다.

빌드 backend는 재현 가능한 배포를 위해 `hatchling==1.31.0`으로 고정한다. 다음 도구는 개발·CI
환경에서만 사용하며 wheel의 runtime dependency나 배포 payload에는 들어가지 않는다.

| 도구 | 용도 | 라이선스 |
| --- | --- | --- |
| Hatchling | wheel·sdist build backend | MIT |
| Ruff | format·lint | MIT |
| mypy | static type check | MIT |
| pytest·pytest-cov | test·coverage runner | MIT |
| coverage.py | branch coverage 측정 | Apache-2.0 |

의존성 감사의 공개 기준은 package metadata의 `Requires-Dist`가 0개인 것이다. 개발 도구 버전은
`uv.lock`, 빌드 backend 버전은 `pyproject.toml`에 고정되며 둘 다 런타임 네트워크 호출을 만들지
않는다.

## corpus·benchmark drift gate

전체 pytest gate는 공개 corpus schema·중복 ID·span·split 계약, 고정 외부 source와 license hash,
사전 provenance, ablation configuration hash를 검사한다. benchmark test는 corpus의 정렬된 전체
case fingerprint가 Windows 기준선과 일치하는지 확인한다. 따라서 corpus나 workload를 의도적으로
바꿀 때는 데이터·benchmark 기준선과 provenance를 같은 변경에서 갱신해야 하며, 단순 파일 교체는
CI에서 실패한다.

## 공개 artifact 경계

wheel은 `koguard` runtime과 dist-info만 포함한다. 필수 runtime dependency는 0개이며 모델,
네트워크 client, evaluation runner, corpus 원문은 포함하지 않는다. 기본 사전에 포함된 Korcen
선별 literal의 MIT 고지는 `NOTICE.md`와 `KORCEN-MIT.txt`, Curse-detection-data에서 독립 검토
후 승격한 4개 literal의 고지는 `NOTICE.md`와 `CURSE-DETECTION-DATA-MIT.txt`로 보존한다.

sdist는 재현에 필요한 테스트, 공개 corpus, benchmark, 평가 도구, provenance metadata와 release
감사 도구를 포함한다. 다음은 포함하지 않는다.

- hidden/private/protected corpus
- annotation work와 quarantine 원문
- tuning 원문
- 외부 `Dataset.csv`, `dataset.txt`
- model weight, pickle, ONNX 등 실행 가능하거나 대용량인 데이터 artifact

`python -m release.artifact_audit`는 wheel/sdist metadata가 `koguard 0.1.0`, Python
`>=3.11,<3.12`, project license, runtime dependency 0개와 일치하는지 확인한다. 실제 파일명,
크기와 SHA-256을 JSON으로 기록하고 wheel 256 KiB, sdist 2 MiB 상한을 적용한다. archive 경로
탈출, 중복 member, wheel의 예상 밖 top-level payload와 sdist의 symlink도 차단한다.
`python -m release.clean_install_smoke`는 각 artifact를 별도 임시 환경에 `--offline --no-deps`로
설치한 뒤 기본 사전 로드와 `contains()`·`check()` quickstart를 isolated Python으로 실행한다.

## 외부 출처 최종 판정

| source | 고정 revision | 공개 payload | 판정 |
| --- | --- | ---: | --- |
| Koguard code·curated defaults | `0.1.0 release tree` | code·기본 데이터 | 소유자 MIT 승인 |
| Tanat05/korcen | `eecd9763dbdccce3dc96ddb578ef0b6396058fa9` | 선별 literal·MIT 고지 | 승인 |
| 2runo/Curse-detection-data | `ff241621e103b6f220d30de324d0d07987887308` | 검토된 literal 4개·MIT 고지 | 원문 제외 조건으로 승인 |
| Tanat05/korean-profanity-resources | `289ed960d10a9e6e3096090fba012ca0796fc641` | 없음 | discovery reference만, 목록 권리 pending |
| ZIZUN malicious comments | `50b92f50e89bb594db5c9ecafea8d48c1dd5b943` | raw 원문 없음 | local quarantine만, 재배포 pending |
| kocohub/korean-hate-speech | `f8d05dce2b22007bb149e5139c0060c68ad8f94b` | 없음 | CC-BY-SA-4.0 provenance reference만 |

`korean-profanity-resources`에는 루트 LICENSE가 없고 자체 `slang.csv`와 LoL 목록을
`확인 필요`로 표시한다. 따라서 해당 두 파일을 복사하지 않는다. ZIZUN 저장소는 MIT 파일을
제공하지만 README상 CC-BY-SA-4.0 자료를 포함하고 행별 provenance가 없어 공개 corpus로
승격하지 않는다. 이 판정은 법률 자문이 아니라 현재 공개 artifact를 보수적으로 제한하는
engineering release gate다.

상세 provenance와 기존 hash는 [`source-rights-audit.md`](source-rights-audit.md), 기계 판정은
`release/rights-manifest.v1.json`을 따른다.

## 남은 공개 gate

소유자는 2026-08-18 Koguard 코드와 직접 작성한 기본 term·Alias를 MIT로 공개하도록 승인했고,
`s23019`가 동일인의 이전 Git identity임을 확인했다. root `LICENSE`, Core Metadata,
rights manifest와 `.mailmap`에 이 결정을 반영했다. 남은 gate는 세 OS 원격 CI, TestPyPI 설치
smoke와 최종 artifact hash 확인이다. 2026-08-18 로컬에서는 format, lint, mypy,
620개 pytest, branch coverage 95.62%, provenance, build, artifact audit와 wheel/sdist clean-install을
통과했다. provisional tuning corpus는 `gold_ready=false`로
유지하며 hidden evaluation 부재를 `0.1.0`의 알려진 품질 한계로 공개한다.
