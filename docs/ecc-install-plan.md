# ECC 프로젝트 적용 계획

이 문서는 Everything Claude Code(ECC)를 Koguard에 맞게 선별한 `agent-sort` 결과다.
ECC 전체를 복제하지 않고 실제 저장소 근거가 있는 표면만 매 세션의 DAILY 규칙으로 사용한다.
원본 프로젝트는 [Everything Claude Code](https://github.com/affaan-m/ECC)이며 MIT
라이선스로 공개되어 있다.

## STACK

- 언어와 런타임: Python 파일 18개, CPython 3.11.9
- 패키지 관리와 빌드: `uv.lock`, uv, Hatchling
- 품질 도구: Ruff, mypy strict, pytest, pytest-cov
- 제품 표면: 네트워크 의존성이 없는 한국어 욕설 탐지 라이브러리
- 현재 UI·웹 프레임워크·데이터베이스·배포 서비스 통합 없음

## DAILY

| ECC 표면 | 유형 | 저장소 근거 | 적용 |
| --- | --- | --- | --- |
| `tdd-workflow` | skill | `tests/`와 90% branch coverage 게이트 | 기능·수정 시 사용 |
| `error-handling` | skill | 공개 예외와 입력 검증 테스트 | 실패 계약 변경 시 사용 |
| `verification-loop` | skill | Ruff, mypy, pytest, build 명령 존재 | 중요한 변경 완료 후 사용 |
| `git-workflow` | skill | `dev`, `feature/*`, `main` 브랜치 운영 | 브랜치·커밋 작업 시 사용 |
| `agent-self-evaluation` | skill | 다중 파일 변경의 전달 품질 점검 | 비단순 작업 완료 후 사용 |
| `koguard_explorer` | agent | engine, matcher, dictionary 호출 경로 | 구현 전 영향 범위 조사 |
| `koguard_reviewer` | agent | span, Whitelist, 결정성 도메인 규칙 | 구현 후 읽기 전용 리뷰 |
| `koguard_docs_researcher` | agent | Python/uv/API/라이선스 검증 필요 | 변경 가능한 사실 조사 |
| `AGENTS.md` | rule | Python 3.11.9, uv, 도메인 불변 조건 | 매 세션 저장소 기본 규칙 |

## LIBRARY

| ECC 그룹 | 저장소 근거 | 결정 |
| --- | --- | --- |
| frontend, browser, E2E | React/Next.js/HTML UI 및 Playwright 설정 없음 | 필요 시 검색 |
| backend API, database | HTTP API, DB, 캐시 의존성 없음 | adapter 단계에서 재평가 |
| 콘텐츠, 투자, 소셜, 미디어 | 제품 개발 범위와 무관 | 전역 라이브러리로만 유지 |
| 외부 API 통합 | Claude, X, fal.ai 의존성 없음 | 해당 기능 요청 시 사용 |
| production audit | 아직 배포 파이프라인 없음 | v1.0 배포 단계에서 승격 검토 |
| AI eval, regression | 현재 core가 결정적 규칙 엔진 | AI plugin 단계에서 승격 검토 |
| browser/MCP extras | 현재 core 작업에 원격 데이터 불필요 | 프로젝트 설정에 활성화하지 않음 |

## INSTALL PLAN

- 프로젝트에 `AGENTS.md`, Codex 역할 설정, 탐색·개발·리뷰 문서를 둔다.
- ECC 스킬 본문은 사용자 스킬 저장소에 이미 있으므로 프로젝트에 중복 복제하지 않는다.
- 프로젝트 `.codex/config.toml`에는 안전한 sandbox와 읽기 전용 역할만 정의한다.
- 모델, 알림, 프로필, MCP, 자격 증명은 사용자 전역 설정을 보존한다.
- LIBRARY용 별도 router는 현재 전역 skill discovery가 제공되므로 만들지 않는다.

## VERIFICATION

- TOML 구문과 프로젝트 설정 로딩 가능 여부
- 모든 문서 링크와 역할 파일 존재 여부
- Ruff format/check, mypy, pytest coverage, wheel/sdist build
- diff의 비밀정보, 원격 MCP, OS 전용 hook, 특정 모델 고정 여부

ECC 업데이트는 원본 파일을 덮어쓰지 않고 새 패턴이 Koguard의 반복 문제를 줄이는지 확인한 뒤
수동으로 반영한다.
