# PF-013 release hardening TDD 증거

## RED

`tests/test_release_hardening.py`를 먼저 추가했을 때 `release` 검증 모듈이 없어 collection이
실패했다. 모듈과 정책 파일을 추가한 다음에는 10개 targeted test 중 8개가 통과하고 다음 두
license gate만 실패하도록 분리했다.

- `pyproject.toml`에 Koguard 자체 project license가 없음
- `release/rights-manifest.v1.json`의 project license가 `UNDECIDED`

외부 Korcen MIT 파일이 존재해도 Koguard 코드와 직접 작성한 term·Alias에 대한 권리 부여를
대신하지 않으므로 이 두 실패를 테스트 완화로 제거하지 않는다.

## 구현 계약

- Ubuntu, Windows, macOS와 CPython 3.11.9 CI matrix
- full commit SHA에 고정한 checkout, setup-python, setup-uv, upload-artifact action
- frozen dependency sync, format, lint, mypy, pytest, provenance, build 순서
- wheel/sdist의 이름, version, Python 범위, license expression, runtime dependency 검증
- wheel에서 evaluation·test·model·raw dataset payload 차단
- sdist에서 hidden/private/quarantine/tuning 원문 차단
- artifact별 크기와 SHA-256 JSON 기록
- wheel 256 KiB·sdist 2 MiB 상한과 archive 경로·member allowlist 검증
- wheel과 sdist를 각각 임시 환경에 `--offline --no-deps` 설치하고 기본 quickstart 실행
- SECURITY, CONTRIBUTING, CHANGELOG와 외부 source 권리 판정 제공

## 실제 clean-install 체크포인트

license metadata를 추가하기 전의 중간 build에서도 설치 경로 자체를 검증했다. wheel과 sdist는
각각 별도 임시 환경에 설치됐고 `KoguardEngine()` 기본 사전, `contains()`와 `check()` probe가
통과했다. 최종 license 결정 뒤 같은 build에서 artifact audit과 smoke를 함께 다시 실행한다.

## 남은 GREEN 조건

소유자가 project license를 승인하면 root LICENSE, Core Metadata, rights manifest와 NOTICE를 같은
변경으로 맞춘다. 그 뒤 targeted test, 전체 품질 gate, build, artifact audit, 두 clean-install을
모두 다시 실행해야 PF-013 feature commit을 완료한다.

## 2026-08-18 GREEN 진행

소유자가 MIT를 승인하고 `s23019`가 동일인의 이전 Git identity라고 확인했다. root `LICENSE`,
PEP 639 metadata, rights manifest와 `.mailmap`을 추가했다. Hatchling이 동등한 Python 범위를
`<3.12,>=3.11` 순서로 직렬화하는 실제 build 회귀를 재현해 artifact audit가 specifier 순서와
공백을 정규화하도록 수정했다. Curse-detection-data에서 승격한 literal의 MIT 고지도 wheel과
sdist 필수 payload로 강화했다.

사전 승격 후 첫 로컬 재측정에서 `balanced` 최대 입력 p95가 18.2218ms로 15ms 예산을 넘었다.
예산이나 테스트를 완화하지 않고 일반 한글에 Alias 선두 문자가 없을 때 경계 계산을 생략하고,
초성 자모가 없을 때 초성 automaton을 생략하며, segmented profile이 아닐 때 raw 초성 source
probe를 생략했다. 탐지 회귀 44개를 통과한 뒤 같은 corpus 재측정에서 short-chat p95 0.0719ms,
최대 입력 p95 13.053ms로 gate를 회복했다.

최종 로컬 검증에서 Ruff format·lint, mypy strict, 620개 pytest와 branch coverage 95.62%를
통과했다. 이어 provenance 73 candidates/65 packaged literals/5 aliases, wheel·sdist build,
artifact metadata·권리·내용 감사와 두 clean-install quickstart를 통과했다. 최종 공개 hash는
원격 CI와 TestPyPI 전 마지막 재현 build에서 다시 고정한다.

2026-08-19 추가 승격 뒤 provenance 기준은 73 candidates/67 packaged literals/5 aliases로
변경됐다. 앞 문단의 65개 기록은 당시 검증 결과이며, 새 기준은 전체 품질 게이트와 재현
build에서 다시 검증한다.

## 2026-08-19 cross-platform reproducibility hardening

동일 commit의 CI run `32225185730`에서 Linux/macOS hash는 같았지만 Windows wheel·sdist hash가
달랐다. Windows checkout의 CRLF가 source와 data member에 들어간 것을 재현했고, backend 고정만으로
재현 가능하다는 기존 가정을 폐기했다.

RED 테스트는 저장소 전체 canonical LF 정책, 세 OS 후보의 실제 파일/audit hash 비교, hash가 다른
후보 거부, pinned `download-artifact`, 단일 authoritative artifact 이름을 먼저 요구했다.
구현은 matrix 산출물을 3일 보존 검증 후보로 분리하고, 네 번째 필수 CI job에서 세 후보가
byte-identical일 때만 Linux 묶음을 14일 보존 release candidate로 승격한다. TestPyPI/PyPI는 이
단일 묶음만 사용한다.

## 2026-08-20 wheel ZIP creator metadata 정규화

CI run `32332576212`에서 세 OS sdist SHA-256은 모두 같았고 wheel의 모든 member content·CRC·압축
크기도 같았다. Windows가 ZIP `create_system=0`, Linux·macOS가 `3`을 기록한 차이만으로 Windows
wheel SHA-256이 달라졌다. RED 테스트는 이 두 wheel이 정규화 후 byte-identical하고 같은 wheel을
두 번 정규화해도 hash가 바뀌지 않을 것을 먼저 요구했다.

`release.normalize_wheel`은 build 직후 archive comment와 각 member의 content·순서·timestamp·권한을
보존하면서 `create_system=3`으로 다시 쓴다. 실패 run에서 내려받은 세 실제 wheel에 적용했을 때
모두 `dbea839233d38b7d65c8769843478e0dfef3f4e5796417e72eee82e737314231`로 수렴했다. CI는
정규화 뒤에만 artifact audit, clean-install, upload와 byte 비교를 수행한다.

## 2026-08-26 tuning corpus sdist 제외 강화

CI run `32824642090`의 세 OS job은 새로 추가된
`evaluation/corpus/tuning/curated-hard-negative-buffer-v1.json`이 sdist에 포함돼 artifact
audit에서 실패했다. 기존 Hatch 설정은 당시 존재하던 tuning 파일만 하나씩 제외해 새 파일이
추가될 때마다 공개 artifact 누출이 재발할 수 있었다.

RED 테스트는 sdist 설정이 개별 파일 목록이 아니라 `/evaluation/corpus/tuning` 전체를 제외할
것을 먼저 요구했다. 구현은 기존 다섯 파일별 예외를 디렉터리 경계 하나로 교체했다. 공개 가능한
source spec, schema와 aggregate report는 tuning 원문 경로 밖에 있으므로 계속 sdist에 포함된다.
