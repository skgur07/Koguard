# Codex 저장소 탐색 가이드

## 빠른 지도

| 경로 | 소유 영역 |
| --- | --- |
| `src/koguard/__init__.py` | 공개 import 표면과 버전 |
| `src/koguard/config.py` | 입력 제한과 정규화 설정 |
| `src/koguard/models.py` | 공개 결과 모델과 불변 조건 |
| `src/koguard/engine/engine.py` | 탐지 파이프라인 조립과 공개 `check` |
| `src/koguard/engine/dictionary.py` | 사전 로딩, 정규화, 결정적 순서 |
| `src/koguard/engine/matcher.py` | Exact 후보와 Whitelist 구간 처리 |
| `src/koguard/engine/normalizer/` | 정규화 view와 원문 인덱스 매핑 |
| `src/koguard/data/` | 기본 사전, Whitelist, 출처 고지 |
| `tests/` | 공개 계약과 회귀 테스트 |
| `tests/corpus/` | 정확도 기준 corpus |
| `docs/implementation-plan.md` | 단계별 제품 및 아키텍처 계획 |
| `docs/accuracy-baseline.md` | 현재 정확도 기준선 |

## 탐색 순서

1. 요청과 직접 관련된 공개 API 및 테스트를 먼저 찾는다.
2. `engine.py`에서 실제 호출 경로를 따라 matcher, dictionary, normalizer로 내려간다.
3. 모델 불변 조건과 예외 계약을 확인한다.
4. 구현 전 관련 corpus와 Whitelist 사례를 확인한다.
5. 변경 후 직접 관련 테스트에서 전체 품질 게이트로 범위를 넓힌다.

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
