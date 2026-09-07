# Koguard 기획 검토 및 구현 계획

기준 문서: 사용자 제공 기획 문서 v2

## 1. 검토 결론

Engine과 Adapter를 분리하고, 사전 기반의 저비용 단계부터 선택적 AI Plugin까지 순차 실행하는
아키텍처 방향은 유지한다. 다만 2026-08-12 제품 재검토에서 탐지 데이터, 독립 평가 corpus,
단순 API와 안전한 기본값이 외부 통합보다 우선이라는 결정을 내렸다. 따라서 기존 Phase 4~6은
보류하고 최초 공개 `0.1.0` 전까지 [제품 집중 계획](product-focus-plan.md)의 Q0~Q4를 현재
실행 로드맵으로 사용한다.

아래 Phase 4~6 내용은 폐기된 설계가 아니라 재개 조건을 충족한 뒤 검토할 설계 초안이다.
런타임 네트워크 의존성을 없애고 결과 캐시를 도입하지 않는 결정도 그대로 유지한다.

다만 현재 문서만으로는 문장 안에서 발견된 여러 단어의 처리, 화이트리스트가 보호할 범위, 정규화 과정에서 원문 위치를 보존하는 방법, 유사도 탐색의 후보 생성 방법이 명확하지 않다. 이 항목은 탐지 정확도와 공개 API에 직접 영향을 주므로 v0.1 구현 전에 아래 권고안으로 확정한다.

## 2. 구현 전 확정할 설계

### 2.1 프로젝트 이름 — 확정

프로젝트 명칭은 다음과 같이 통일한다.

- 프로젝트/제품명: `Koguard`
- PyPI 배포명: `koguard`
- Python import 이름: `koguard`
- 기본 Engine 클래스: `KoguardEngine`
- 실제 배포 전 PyPI 이름 사용 가능 여부와 상표 충돌 가능성을 별도로 확인한다.

### 2.2 탐지 결과 모델

문장에는 여러 매치가 존재할 수 있으므로 단일 `matched_word`만으로는 부족하다. v0.1부터 상세 매치 모델을 둔다.

```python
@dataclass(frozen=True, slots=True)
class Match:
    term: str
    matched_text: str
    start: int | None
    end: int | None
    method: MatchMethod
    score: float


@dataclass(frozen=True, slots=True)
class CheckResult:
    detected: bool
    normalized_text: str
    matches: tuple[Match, ...]
    elapsed_ms: float
```

다중 `matches`가 필요한 이유는 다음과 같다.

1. 한 문장에 욕설이 여러 개 있을 수 있다. 단일 `matched_word`는 첫 번째 항목만 보여 주므로 나머지를 잃는다.
2. 화이트리스트는 문장 전체가 아니라 특정 구간만 보호해야 한다. 보호된 단어와 실제 욕설이 같은 문장에 있으면 보호된 구간만 제외하고 나머지는 반환해야 한다.
3. 서로 다른 탐지 단계가 각기 다른 구간을 발견할 수 있다. 각 매치에 method와 score를 붙여야 호출자가 차단, 마스킹, 검토 같은 정책을 선택할 수 있다.
4. 채팅을 마스킹하려면 원문의 모든 탐지 위치가 필요하다. 단일 단어만으로는 같은 단어의 반복이나 정규화된 우회 표현을 정확히 치환하기 어렵다.

예를 들어 화이트리스트에 `시발점`이 있고 입력이 `시발점과 병신이라는 표현`이라면 `시발점` 내부의 겹치는 후보는 제외하고 두 번째 구간만 반환한다.

```python
result.detected  # True
result.matches   # (Match(term="병신", start=5, end=7, method=MatchMethod.EXACT, ...),)
```

반환 규칙은 다음과 같이 고정한다.

- `detected`는 `bool(matches)`와 항상 같다.
- 매치는 원문 `start` 오름차순, 같은 위치에서는 긴 구간 우선, 그래도 같으면 matcher 우선순위 순으로 정렬한다.
- 동일하거나 겹치는 블랙리스트 후보는 기본적으로 가장 긴 구간 하나만 남긴다. 단, 서로 독립된 구간은 모두 남긴다.
- 화이트리스트와 겹치는 후보는 해당 후보만 제거하고 다른 매치에는 영향을 주지 않는다.
- 기존의 단일 `matched_word`, `method`, `confidence`가 필요하면 첫 번째 매치에서 계산하는 호환 프로퍼티로 제공할 수 있지만, 새 코드는 `matches`를 사용한다.

- `start`와 `end`는 가능한 경우 원문 기준 반열림 구간(`[start, end)`)으로 반환한다.
- 정규화 때문에 원문 위치를 정확히 복원할 수 없는 Plugin은 위치를 `None`으로 반환할 수 있다.
- `matched_word`, `method`, `confidence` 같은 단일 필드는 필요하면 첫 번째 또는 최고 점수 매치에서 계산하는 읽기 전용 호환 프로퍼티로 제공한다.
- `confidence`는 통계적으로 보정된 확률로 오해될 수 있으므로 초기에는 `score`라는 이름을 권장한다.
- `MatchMethod.NONE`은 개별 매치에는 사용하지 않는다. 미탐지는 빈 `matches`로 표현한다.

### 2.3 점수 규칙

- EXACT/TRIE: `1.0`
- LEVENSHTEIN: `1 - distance / max(len(candidate), len(term))`
- EMBEDDING: Plugin이 `[0.0, 1.0]` 범위의 점수를 반환하되, 모델별 임계값과 점수 의미를 Plugin 문서에 명시한다.
- 점수는 서로 다른 method 사이에서 확률처럼 직접 비교하지 않는다.

### 2.4 정규화

하나의 문자열을 계속 파괴적으로 변환하지 않고 목적별 정규화 view를 만든다. 그래야 오탐을 줄이고 원문 위치를 추적할 수 있다.

1. Unicode 정규화(NFC 또는 NFKC 정책 확정), 제로폭 문자 제거
2. 대소문자와 공백 표준화
3. 반복 문자 축약 view
4. 특수문자 사이를 결합한 우회 탐지 view
5. 영문 자판→한글 변환 view
6. 초성 비교 view

각 view는 가능하면 원문 인덱스 매핑을 함께 유지한다. 자판 변환과 초성 변환은 오탐 위험이 크므로 기본 view를 대체하지 않고 추가 탐색 view로만 사용한다. 반복 허용 개수, 결합할 특수문자, 최대 입력 길이는 `EngineConfig`로 관리한다.

### 2.5 Exact index와 Whitelist 의미

- Exact는 입력 문장 전체가 아니라 토큰 또는 사전 term과 동일한 구간을 찾는 단계로 정의한다.
- Exact index는 실제 사전 크기와 입력 corpus를 벤치마크해 선택하며 longest-match-first 규칙을
  유지한다. Python prefix Trie 시제품은 작은 사전과 긴 입력에서 `str.find` 기반 검색보다
  느려 런타임 경로에서 제외했다.
- 화이트리스트는 결과 전체를 무효화하지 않고 겹치는 블랙리스트 매치 구간만 보호한다. 예를 들어 `시발점` 안의 매치는 제외하되 같은 문장의 다른 욕설은 계속 반환한다.
- 블랙리스트와 화이트리스트가 완전히 같은 term을 포함하면 화이트리스트가 우선한다.
- 화이트리스트 판정은 각 정규화 view에서 동일한 규칙으로 수행한다.

### 2.6 Levenshtein 후보 탐색

일반 Trie 탐색 결과만으로 후보를 좁히면 철자 누락이나 첫 글자 변형을 놓친다. 다음 중 하나를 벤치마크 후 채택한다.

- Trie 위에서 동적 계획법 행을 전파하는 fuzzy trie 탐색
- 길이 버킷 + 첫/끝 글자 등 저비용 인덱스로 후보를 좁힌 뒤 편집거리 계산
- 데이터가 커질 경우 BK-tree 또는 SymSpell 계열 인덱스

거리 기준은 `max(len(candidate), len(term))`을 기준으로 적용한다. 1~2자 단어에 distance 1을 허용하면 오탐이 급증하므로 기본값은 exact-only로 두고, 3~4자부터 distance 1을 허용한다. 최종 임계값은 실제 사전과 검증 corpus로 조정한다.

### 2.7 Plugin과 비동기 처리

`KoguardEngine.check()`는 동기 API로 유지한다. 동기 Plugin만 Engine pipeline에 등록하며, Adapter의 비동기 진입점은 전체 `engine.check()`를 `asyncio.to_thread()`로 오프로딩한다.

외부 HTTP API처럼 본질적으로 비동기인 Plugin이 필요해지는 시점에는 `AsyncPlugin`과 `acheck()`을 별도 계약으로 추가한다. v0.5의 `BasePlugin`에는 다음 정책도 포함한다.

- 실행 순서와 조기 종료 여부
- Plugin 실패 시 fail-open/fail-closed 정책
- timeout과 예외 래핑
- Plugin이 반환할 수 있는 method와 score 범위
- thread-safety 요구사항

### 2.8 Dictionary와 데이터

- `importlib.resources`로 패키지 내부 UTF-8 데이터를 읽는다.
- 로드한 set/trie는 결과 캐시가 아니라 불변 검색 인덱스라는 용어를 사용한다.
- 사용자 정의 사전은 파일 경로와 iterable 양쪽을 지원하고, 기본 사전에 추가할지 교체할지 명시한다.
- 빈 줄, 주석, 중복, Unicode 정규화, 충돌을 build 단계에서 검사한다.
- 초기 구현에서는 직접 작성한 최소 fixture와 배포하지 않는 로컬 데이터로 기능을 검증한다.
- 데이터셋 라이선스와 재배포 가능 여부 검토는 초기 구현의 차단 조건에서 제외하되, 외부 데이터는 검토가 끝날 때까지 wheel이나 공개 저장소에 포함하지 않는다.
- PyPI 배포 전 원본 데이터셋 URL, commit/hash, 라이선스, 변환 규칙을 `data/NOTICE.md`와 manifest에 기록한다.
- 런타임 로그에는 기본적으로 입력 원문을 남기지 않는다.

### 2.9 Adapter 범위

`socket`, `websocket`, `fastapi`는 서로 메시지 경계와 프레임워크가 달라 범용 wrapper가 되기 어렵다.

- FastAPI: 재사용 가능한 dependency 또는 요청/응답 helper와 예제 제공
- WebSocket: 메시지 문자열을 검사하는 handler decorator/helper 제공
- Raw socket: framing을 라이브러리가 추측하지 않고 사용자가 decoder/callback을 주입하는 helper 제공

각 Adapter는 Engine을 변경하거나 monkey patch하지 않는다. FastAPI/WebSocket 같은 선택 의존성은 `project.optional-dependencies`의 extra로 분리한다.

## 3. 비기능 요구사항

- 개발 및 검증 기준 Python은 CPython 3.11.9로 고정한다. `.python-version`은 정확히 `3.11.9`, 패키지 metadata는 같은 minor의 보안 패치 버전을 막지 않도록 `>=3.11,<3.12`로 설정한다.
- 최대 입력 길이를 설정하고 초과 시 명시적인 예외 또는 잘림 없는 거부 결과를 반환한다.
- Dictionary와 Engine은 생성 후 읽기 전용으로 만들어 여러 thread에서 안전하게 공유한다.
- 동일 입력과 동일 설정은 항상 동일한 매치 순서를 반환한다.
- 시간 측정은 `time.perf_counter_ns()`로 항상 수행한다. Dictionary 탐색 비용과 비교해 오버헤드가 작으며 API를 단순하게 유지할 수 있다.
- `py.typed`를 포함하고 공개 API에 타입 힌트를 제공한다.
- 100% line coverage 자체보다 branch coverage, 오탐/미탐 corpus, 성능 회귀 기준을 품질 지표로 사용한다.

## 4. 권장 프로젝트 구조

```text
Koguard/
├── src/koguard/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── py.typed
│   ├── engine/
│   │   ├── engine.py
│   │   ├── dictionary.py
│   │   ├── matcher.py
│   │   ├── pipeline.py
│   │   └── normalizer/
│   ├── plugins/
│   │   └── base.py
│   ├── adapters/
│   └── data/
│       ├── badwords.txt
│       ├── whitelist.txt
│       └── NOTICE.md
├── scripts/
│   └── build_dictionary.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── corpus/
│   └── benchmarks/
├── docs/
├── pyproject.toml
└── uv.lock
```

## 5. 단계별 구현 계획

### Phase 0 — 기반 정리

작업:

- 프로젝트명, 배포명, import 이름을 `Koguard`/`koguard`로 통일
- CPython 3.11.9 개발 환경 고정
- `uv` 기반 `src` layout과 build backend 구성
- Ruff, mypy 또는 Pyright, pytest, pytest-cov 설정
- 공개 API/예외/config 초안 작성

완료 조건:

- `uv sync --all-extras --dev` 성공
- `uv run python --version`이 `Python 3.11.9`를 출력
- 빈 패키지의 build와 import 성공
- lint, type check, test 명령이 로컬에서 모두 통과

### Phase 1 — v0.1 Exact + Whitelist

작업:

- `Match`, `CheckResult`, `MatchMethod`, `EngineConfig` 구현
- 패키지 데이터 로더와 사용자 사전 주입 구현
- 최소 Unicode/공백 정규화 및 인덱스 매핑 구현
- token/구간 Exact 탐색과 span 단위 whitelist 보호 구현
- `KoguardEngine.check(text)` 구현

테스트:

- 빈 문자열, 잘못된 타입, 매우 긴 입력
- 단일/복수 매치와 매치 순서
- `시발점`처럼 화이트리스트가 substring 오탐만 제거하는 사례
- 화이트리스트 단어와 실제 욕설이 한 문장에 같이 있는 사례
- 데이터 중복, 충돌, 잘못된 encoding
- 동시 호출 시 결과 일관성

완료 조건:

- 원문 span을 포함한 결과가 명세대로 반환됨
- corpus 기반 Exact precision/recall 기준선 기록
- wheel에 기본 사전과 `py.typed`가 포함됨

### Phase 2 — v0.2 Normalizer + Exact Index + Benchmark

상태: 완료 (2026-08-10)

작업:

- 반복 문자, 특수문자 우회, 자판, 초성 view를 각각 독립 단계로 구현
- longest-match-first Exact index 구현 및 후보 선택 비용 최적화
- 정규화 view별 원문 위치 매핑
- pytest-benchmark 또는 별도 benchmark CLI 구성

성능 corpus:

- 짧은 채팅, 1 KB, 최대 허용 길이 입력
- 사전 크기별 cold start와 steady-state 처리량
- 정상 문장과 다수 후보를 만드는 적대적 입력

완료 조건:

- 정확도 corpus에서 단계별 오탐/미탐 변화가 수치로 기록됨
- 기준 장비와 Python 3.11.9를 명시한 p50/p95 결과 저장
- 이후 PR에서 비교할 benchmark baseline 확보

### Phase 3 — v0.3 Fuzzy Matching

상태: 완료 (2026-08-11)

작업:

- 후보 생성 방식 2개 이상 prototype/benchmark
- 선택된 인덱스와 Levenshtein score 구현
- 짧은 단어 보호 규칙과 설정 가능한 거리/score threshold 구현
- fuzzy 단계의 계산량 제한 구현

완료 조건:

- 오타/변형 corpus recall 개선 확인
- 정상 문장 false-positive 예산을 넘지 않음
- 최대 입력에서 시간/메모리 상한을 만족

구현 결과:

- 길이 버킷 전수 비교와 deletion-signature index를 1,000개 합성 사전에서 비교했다. 동일
  길이의 미탐 probe 100회 기준 중앙값은 각각 18.4393ms와 0.0020ms여서 삭제 서명 index를
  채택했다.
- 기본값은 3~32글자 독립 영숫자 토큰, 편집거리 1이며 거리 2와 최소 score까지 명시적으로
  설정할 수 있다.
- `fuzzy_max_operations`는 check별 서명 생성·조회, 조회 후보 수와 DP cell 계산을 제한하며
  초과 시 부분 결과 대신 `FuzzyOperationLimitError`를 발생시킨다.
- `fuzzy_max_index_entries`는 Engine 생성 시 index 메모리 증가를 제한한다.
- Fuzzy는 모든 규칙 기반 매치 뒤에 실행하고 기존 Whitelist 및 점유 구간을 존중한다.
- 12문장 수동 corpus의 FP/FN은 0이며, 1,000개 사전·4,096자 Fuzzy 전용 정상 입력 기준은
  p50 4.6675ms, p95 5.7893ms다.

### 품질 집중 트랙 Q0~Q4 — 최초 공개 0.1.0

상태: **진행 대상**

기존 Phase 4보다 먼저 다음 순서로 실행한다.

1. Q0: corpus schema, 비교 runner, 현재 matcher ablation
2. Q1: 독립 평가 corpus와 출처가 추적되는 탐지 데이터 확장
3. Q2: `strict`·`balanced`·`aggressive` profile과 `contains()` API
4. Q3: Unicode·오탐·성능, CI·패키징·라이선스 hardening
5. Q4: TestPyPI 검증과 `0.1.0` 공개 판정

세부 작업, 수치화 방법, 우선순위와 완료 조건은
[제품 집중 계획](product-focus-plan.md)을 단일 기준으로 사용한다.

### Phase 4 — v0.4 Adapters

상태: **보류 (2026-08-12)**

Q2에서 core API가 안정되고 Q3 품질 게이트를 통과한 뒤, 최소 두 실제 통합에서 같은
boilerplate 문제가 확인될 때만 재개한다. 재개 시에도 가장 수요가 큰 adapter 하나부터
추가한다.

작업:

- 공통 adapter 결과/오류 정책 정의
- FastAPI dependency/helper 및 async offload 구현
- WebSocket handler helper 구현
- decoder/callback 기반 raw socket 예제 구현
- optional extra와 통합 테스트 추가

완료 조건:

- event loop를 블로킹하지 않는 통합 테스트 통과
- Engine 단독 설치에는 프레임워크 의존성이 포함되지 않음
- Adapter가 Engine 내부 상태를 수정하지 않음

### Phase 5 — v0.5 Plugin System

상태: **보류 (2026-08-12)**

core matcher 계약이 안정되고, 서로 다른 두 종류 이상의 외부 detector 요구와 단순 callback을
넘는 timeout·ordering·오류 정책이 실제로 확인될 때만 재개한다.

작업:

- `BasePlugin`, `PluginManager`, 오류/timeout/순서 정책 구현
- 예제 경량 Plugin과 contract test kit 제공
- 동기 Plugin의 Adapter offload 검증

완료 조건:

- Plugin 미설치 시 core import/startup 비용 변화가 거의 없음
- Plugin 오류 정책과 deterministic ordering 테스트 통과

### Phase 6 — v0.6 Embedding Plugin

상태: **보류 (2026-08-12)**

독립 evaluation에서 규칙과 데이터 확장으로 해결되지 않는 false-negative cluster가 반복
확인되고, 합법적인 평가 데이터와 recall·오탐·지연·메모리·배포 크기 예산이 준비될 때만
재개한다.

작업:

- 별도 extra로 BGE 계열 Plugin 구현
- 모델 lazy loading, 장치 선택, batch 처리, threshold 설정
- 모델 식별자와 다운로드/오프라인 동작 문서화
- 모델별 평가 corpus와 score calibration 수행

완료 조건:

- core wheel에는 모델/ML 의존성이 포함되지 않음
- 모델 부재, offline, CPU-only 환경의 오류 메시지가 명확함
- Exact/Trie/Fuzzy 대비 추가 recall과 지연 비용이 측정됨

### Phase 7 — v1.0 배포

상태: **분할**

core의 CI, 패키징, 라이선스 감사와 clean-install 검증은 품질 집중 트랙 Q3~Q4로 앞당긴다.
Adapter·Plugin·모델을 전제로 한 배포 항목은 각 보류 Phase가 재개될 때까지 진행하지 않는다.

작업:

- GitHub Actions에서 OS/Python matrix 테스트, lint, type check, build 수행
- `python -m build`, wheel/sdist 설치, `twine check` 검증
- 코드, 사전 데이터, 모델과 의존성의 라이선스 및 재배포 조건 검토
- 데이터와 모델의 출처, commit/hash, 변환 규칙을 NOTICE에 기록
- API 문서, migration 정책, changelog, 보안/기여 가이드 작성
- TestPyPI smoke test 후 trusted publishing 설정

완료 조건:

- 깨끗한 환경에서 README quickstart 재현
- wheel/sdist 모두 설치 및 기본 사전 로드 성공
- 공개 API, 데이터 출처, 성능/정확도 한계가 문서화됨

## 6. 테스트 및 품질 전략

테스트는 코드 단위뿐 아니라 데이터 품질을 중심으로 구성한다.

- Unit: normalizer 단계, span mapping, dictionary 충돌, matcher 경계값
- Property-based: Unicode/공백/특수문자 변형에도 crash하지 않고 결과가 deterministic한지 검증
- Corpus: true positive, false positive, whitelist, obfuscation을 분리하고 기대 결과를 versioning
- Integration: 패키지 리소스, optional extras, adapter, wheel 설치
- Performance: p50/p95, 처리량, peak memory, import/startup 시간

모든 성능 수치는 목표 장비 없이 먼저 약속하지 않는다. v0.1에서 기준선을 얻고 v0.2부터 허용 회귀율을 정한다.

## 7. 결정 현황

확정된 결정:

1. 프로젝트, 배포, import 이름은 `Koguard`/`koguard`로 통일한다.
2. 개발 Python은 CPython 3.11.9로 고정한다.
3. 라이선스 검토는 초기 기능 구현 이후로 미루되, 검토되지 않은 외부 데이터나 모델은 공개 배포물에 넣지 않는다.
4. Phase 2 후속 정규화에서는 공백이나 구분자를 전역 제거하지 않고, 입력 길이와 구간 크기를
   제한한 조합 view로 다음 표현을 탐지한다.
   - 분리된 초성: `ㅅ ㅂ`, `ㅅ*ㅂ`
   - 분리된 호환 자모: `ㅅㅣ ㅂㅏㄹ`
   - 구분자가 섞인 영문 두벌식 입력: `tl * qkf`
5. 현재 구현된 규칙 기반 탐지 단계의 개별 설정과 기본값 `True`는 Q2 전까지의 호환 기준선으로
   보존한다. 최초 공개 기본값으로 확정하지 않으며, matcher ablation 뒤 `balanced` profile을
   기본으로 바꾼다. 초성·분리 입력·Fuzzy는 우선 `aggressive` 후보로 둔다. 공백을 전역 제거해
   `시 발표` 같은 정상 문장을 결합하는 구현은 계속 허용하지 않는다.
6. 규칙 기반 탐지로 처리하기 어려운 문맥, 신조어, 미등록 변형이 있다는 이유만으로 AI
   Plugin을 먼저 구현하지 않는다. 독립 evaluation에서 규칙과 데이터로 해결되지 않는 cluster가
   확인되고 [제품 집중 계획](product-focus-plan.md)의 재개 조건을 모두 충족할 때만 별도 extra,
   기본 비활성화와 lazy loading 원칙으로 검토한다.
7. 공개 결과 모델은 불변 `matches: tuple[Match, ...]` 구조를 채택한다. scalar 속성은 첫
   매치 기반 호환 property로 유지한다.
8. 초기 기본 사전은 직접 선별 표현과 고정 revision의 MIT Korcen 일부만 포함한다. 라이선스가
   확인되지 않은 외부 사전은 포함하지 않는다.
9. 패키지 버전은 전체 공개 품질 게이트를 마칠 때까지 `0.1.0`을 유지하고, 공개 범위를 확정한
   뒤 한 번에 다음 버전으로 올린다.

남은 결정:

1. Q1 독립 기준선에서 최초 공개의 slice별 최소 recall과 정상 문장 false-positive 예산을
   확정한다.
2. matcher ablation 결과로 `balanced`에 포함할 탐지 단계를 확정한다.
3. Q1 기준선과 false-negative cluster를 바탕으로 기본 데이터의 coverage 목표를 확정한다.
