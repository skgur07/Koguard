# 반복 모음 우회 탐지 TDD 증거

## 사용자 여정

사전 기반 탐지를 사용하는 운영자로서 `시이이발`, `씨이이발`처럼 앞 음절의 모음을 독립
음절로 반복해 우회한 표현을 탐지하면서도 원문 span, Exact 우선순위, 사용자 Whitelist를
유지하고 싶다.

## 범위와 정책

- 동일 모음의 독립 음절이 연속 2회 이상일 때만 추가 view에서 제거한다.
- 한 번만 추가된 음절은 축약하지 않는다.
- 기본 view를 파괴하지 않고 Exact 결과가 반복 view보다 우선한다.
- 반복 view 매치는 `MatchMethod.REPEATED`로 구분한다.
- 임계값은 `EngineConfig.repeat_reduction_threshold`로 관리하며 최솟값은 2다.

## RED

- 테스트: `tests/test_config.py`, `tests/test_normalizer.py`, `tests/test_engine.py`
- 명령:
  `uv run pytest --no-cov tests/test_config.py tests/test_normalizer.py tests/test_engine.py`
- 결과: `build_repeated_view`가 없어 import 단계에서 의도대로 실패
- 체크포인트: `25775e5 test: 반복 모음 우회 탐지 계약 추가`

## GREEN

- 반복 view와 원문 source span 병합 구현
- Exact·Repeated 결과를 원문 구간 기준으로 통합
- 반복 view에서도 동일 Whitelist 적용
- Hangul 모음 연속이 없는 입력은 정규식 fast path로 기존 view를 즉시 반환
- 명령:
  `uv run pytest --no-cov tests/test_config.py tests/test_normalizer.py tests/test_engine.py`
- 결과: `41 passed`
- 체크포인트: `f455783 feat: 반복 모음 우회 탐지 view 추가`

## 성능 리뷰

초기 구현은 모든 입력에서 반복 view를 복사해 기존 기준선 대비 1.5~1.8배 느렸다. fast path
적용 후 동일 장비·100회 측정의 p50 비교는 다음과 같다.

| case | 기존 | 변경 후 | 배율 |
| --- | ---: | ---: | ---: |
| 1 KB 정상 입력 | 0.5973 ms | 0.6032 ms | 1.01배 |
| 최대 4,096자 | 2.5092 ms | 2.7277 ms | 1.09배 |
| 반복 후보 512자 | 10.3903 ms | 10.1775 ms | 0.98배 |
| 사전 1,000개 | 0.2343 ms | 0.2343 ms | 1.00배 |

짧은 정상 입력은 0.0119 ms에서 0.0138 ms로 증가했으나 절대 증가는 0.0019 ms였다.

## 알려진 제한

현재 view는 완성형 한글 음절 뒤에서 같은 모음의 독립 음절이 반복되는 패턴만 처리한다.
자음 반복, 음절 내부 변형, 특수문자 삽입, 자판 입력, 초성 표현은 후속 view 범위다.
