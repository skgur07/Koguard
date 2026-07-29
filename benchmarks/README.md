# Koguard benchmark

Phase 2 이후의 탐지 기능이 정확성과 성능을 함께 유지하는지 비교하기 위한 로컬 기준선이다.
외부 benchmark 패키지 없이 Python 표준 라이브러리만 사용한다.

## 실행

저장소 루트에서 CPython 3.11.9로 실행한다.

```powershell
uv run python -m benchmarks.engine_benchmark `
  --corpus benchmarks/corpus.json `
  --iterations 100 `
  --warmups 10 `
  --output benchmarks/results/local.json
```

기본 인자를 사용할 때는 다음 명령으로 충분하다.

```powershell
uv run python -m benchmarks.engine_benchmark
```

## Corpus

`corpus.json`은 다음 부하를 고정한다.

- 짧은 정상 채팅과 Whitelist·금칙어 혼합 문장
- 1,024자 정상 입력
- 기본 최대 입력 길이인 4,096자
- 공통 접두사 후보가 대량 생성되는 512자 적대적 입력
- 공백 매칭을 활성화한 `시 발` 탐지와 `시 발표` 경계 오탐 방지
- 공백 매칭과 256개 공통 접두사를 결합한 최대 길이 적대적 입력
- 100개와 1,000개 합성 사전

각 case에는 `expected_matches`가 있다. 탐지 결과가 기대값과 다르면 성능 수치를 저장하지 않고
실패하므로 정확도 회귀를 성능 향상으로 오인하지 않는다.

`engine_profile`은 case마다 사용할 엔진 설정을 지정한다. 생략하거나 `default`이면 기본 설정을
사용하고, `whitespace-gap`이면 `EngineConfig(whitespace_gap_matching=True)`를 사용한다.
`dictionary_profile`은 합성 사전 형태를 지정하며 `standard`, `overlapping-prefix`,
`deep-whitespace-prefix`를 지원한다. 알 수 없는 profile은 측정을 시작하기 전에 실패한다.

## 지표

- `p50_ms`, `p95_ms`: warmup 이후 개별 `engine.check()` 지연 시간의 nearest-rank percentile
- `throughput_per_second`: 측정 반복의 누적 처리 시간에서 계산한 초당 호출 수
- `cold_start_ms`: 사전 생성, Engine 생성, 첫 `check()`까지 한 번 측정한 시간
- `peak_memory_bytes`: 생성된 Engine의 `check()` 한 번에서 `tracemalloc`로 측정한 peak allocation

수치는 OS 스케줄링과 전원 상태의 영향을 받는다. 다른 장비의 절대 수치를 합격 기준으로
사용하지 않고, 동일 장비·Python 버전·corpus에서 변경 전후를 비교한다.

## 기준 결과

`results/windows-python311.json`은 Windows와 CPython 3.11.9에서 100회 측정한 최초 기준선이다.
새 결과를 검토할 때는 환경 메타데이터, 정확도 기대값, p50/p95, peak memory를 함께 비교한다.
report schema 2부터 각 결과에 `engine_profile`, `dictionary_profile`, `case_fingerprint`를
기록한다. fingerprint는 이름, category, 확장된 전체 입력, 사전 크기와 profile, 엔진 profile,
정확도 기대값을 포함하므로 corpus가 바뀐 뒤 이전 기준선을 실수로 사용하는 것을 막는다.
