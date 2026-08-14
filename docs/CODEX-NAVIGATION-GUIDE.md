# Codex 저장소 탐색 가이드

## 빠른 지도

| 경로 | 소유 영역 |
| --- | --- |
| `src/koguard/__init__.py` | 공개 import 표면과 버전 |
| `src/koguard/config.py` | 입력 제한과 정규화 설정 |
| `src/koguard/models.py` | 공개 결과 모델과 불변 조건 |
| `src/koguard/engine/engine.py` | 탐지 파이프라인 조립과 공개 `check`·`contains` |
| `src/koguard/engine/dictionary.py` | 사전 로딩, 정규화, 결정적 순서 |
| `src/koguard/engine/matcher.py` | Exact 후보와 Whitelist 구간 처리 |
| `src/koguard/engine/normalizer/` | 정규화 view와 원문 인덱스 매핑 |
| `src/koguard/data/` | 기본 사전, Whitelist, 출처 고지 |
| `evaluation/` | 평가 corpus, validator, blinded annotation, 비교·ablation runner |
| `tests/` | 공개 계약과 회귀 테스트 |
| `tests/corpus/` | 정확도 기준 corpus |
| `docs/corpus-annotation-guide.md` | label, span, 출처, split annotation 정책 |
| `docs/corpus-split-policy.md` | tuning/hidden/private 접근, 변경 승인과 보존 정책 |
| `docs/corpus-intake-status.md` | PF-005 source pin, review intake와 gold blocker |
| `docs/source-rights-audit.md` | 외부 평가 자료 사용 범위, 고정 근거와 권리 검토 blocker |
| `docs/dictionary-provenance.md` | 사전 후보 source·license·core/AI 경계와 승격 정책 |
| `docs/dictionary-data-changelog.md` | candidate ID 기반 사전 변경과 증분 평가 기록 |
| `evaluation/README.md` | 고정 artifact 기반 비교 실행법, 리포트 계약과 한계 |
| `evaluation/profile_report.py` | 보호 ablation에서 공개 profile 집계만 추출하는 sanitizer |
| `docs/matcher-ablation-baseline.md` | matcher별 provisional 정확도·지연·메모리 근거 |
| `docs/product-focus-plan.md` | 최초 공개 품질 우선순위, Phase 보류와 재개 조건 |
| `docs/profile-api-contract.md` | strict·balanced·aggressive 공개 동작과 이동 계약 |
| `docs/contains-api.md` | boolean 편의 API와 `check()` 동등성·성능 계약 |
| `docs/public-api-inventory.md` | 0.1.0 공개 심볼과 제거·비지원·확장 경계 |
| `docs/unicode-fp-hardening.md` | PF-012 Unicode·오탐 정책, 전후 정확도·성능과 한계 |
| `docs/implementation-plan.md` | 단계별 제품 및 아키텍처 계획 |
| `docs/accuracy-baseline.md` | 현재 정확도 기준선 |

## 탐색 순서

1. 제품 우선순위, corpus, 기본 profile 또는 로드맵 변경은 `product-focus-plan.md`를 먼저 읽는다.
2. 요청과 직접 관련된 공개 API 및 테스트를 찾는다.
3. `engine.py`에서 실제 호출 경로를 따라 matcher, dictionary, normalizer로 내려간다.
4. 모델 불변 조건과 예외 계약을 확인한다.
5. 구현 전 관련 corpus와 Whitelist 사례를 확인한다.
6. 변경 후 직접 관련 테스트에서 전체 품질 게이트로 범위를 넓힌다.

검색은 `rg`와 `rg --files`를 우선하고, 큰 파일을 처음부터 전부 읽기보다 심볼과 호출 경로를
기준으로 필요한 범위를 읽는다.

## 변경 소유권

- 공개 API 변경은 `__init__.py`, 모델, 문서, 테스트를 하나의 계약으로 검토한다.
- 정규화 변경은 matcher 정확도와 원문 span 테스트를 함께 소유한다.
- 사전 변경은 `NOTICE.md`, 배포 라이선스, corpus 결과를 함께 검토한다.
- 성능 최적화는 결정적 결과와 최대 입력 길이 정책을 바꾸지 않아야 한다.

## PR diff packet

PR 또는 최종 전달에는 다음 정보를 한 묶음으로 제공한다.

- 변경 목적과 사용자 관점의 동작 차이
- 핵심 파일과 설계 결정
- 새로 추가하거나 변경한 테스트
- 실행한 포맷, 린트, 타입, 테스트, 빌드 결과
- 정확도, 성능, 라이선스, 호환성의 알려진 위험

finding을 보고할 때는 파일과 좁은 줄 범위, 재현 조건, 실제 영향을 포함한다.
