# Koguard

한국어 욕설·비속어 탐지를 위한 경량 Python 라이브러리입니다.

현재 v0.1에서는 기본 사전 기반 Exact Match, 반복·구분자 우회 view, 공백·혼합·초성 매칭과
구간 단위 Whitelist 처리를 제공합니다. 모든 탐지 단계는 기본으로 활성화되며 단계별로 끌 수
있습니다.

## 사용법

```python
from koguard import KoguardEngine

engine = KoguardEngine()
result = engine.check("검사할 문장")

print(result.detected)
print(result.matches)
```

기본 사전 대신 직접 만든 사전을 사용할 수도 있습니다.

```python
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["금칙어"],
    whitelist=["금칙어가 포함된 정상 표현"],
    include_defaults=False,
)
engine = KoguardEngine(dictionary=dictionary)
```

### 탐지 단계 설정

모든 탐지 플래그는 기본값이 `True`이고 정확한 `bool` 값만 허용합니다.

| 설정 | 탐지 단계 | 기본값 |
| --- | --- | --- |
| `exact_matching` | 정규화된 사전어 Exact Match | `True` |
| `repeated_matching` | `시이이발` 같은 반복 모음 축약 view | `True` |
| `separator_matching` | `시*!발` 같은 설정 구분자 제거 view | `True` |
| `whitespace_gap_matching` | `시 발` 같은 공백·탭 간격 매칭 | `True` |
| `mixed_gap_matching` | `시 * 발` 같은 공백·구분자 혼합 매칭 | `True` |
| `choseong_matching` | `ㅅㅂ` 같은 독립 초성 토큰 매칭 | `True` |

각 단계는 독립적으로 `False`로 끌 수 있습니다. 다음 설정은 Exact Match만 남깁니다.

```python
from koguard import EngineConfig, KoguardEngine

config = EngineConfig(
    exact_matching=True,
    repeated_matching=False,
    separator_matching=False,
    whitespace_gap_matching=False,
    mixed_gap_matching=False,
    choseong_matching=False,
)
engine = KoguardEngine(config=config)
```

기본 사전은 직접 선별한 Exact Match 표현을 포함하며 기본 Whitelist는 비어 있습니다.
따라서 `시발점`, `병신년`처럼 금칙어를 포함한 복합어도 기본 정책에서는 탐지합니다.
서비스 문맥에서 허용할 표현은 `whitelist` 또는 `whitelist_path`로 명시적으로 주입해야 합니다.

앞 음절과 같은 모음의 독립 음절을 두 번 이상 늘인 표현은 반복 문자 view에서 추가로
탐지합니다. 예를 들어 `시이이발`은 `시발`로 탐지되며 결과의 `matched_text`와 span은
원문 전체를 가리킵니다. 한 번만 추가된 `시이발`은 기본값에서 축약하지 않습니다.

문자 사이에 삽입된 `!@#$%^&*_-+=~.·,` 기호는 특수문자 view에서 제거해 탐지합니다.
예를 들어 `시*!발`은 `시발`로 탐지되며 원문 span은 삽입된 기호까지 포함합니다. 제거할
문자 집합은 `EngineConfig.obfuscation_separators`로 제한할 수 있고, 공백이나 영숫자는
구분자로 설정할 수 없습니다.

공백 삽입과 공백·구분자 혼합 우회 탐지는 기본으로 활성화됩니다. 필요하면 서로 독립적으로
끌 수 있습니다.

```python
from koguard import EngineConfig, KoguardEngine

config = EngineConfig(
    whitespace_gap_matching=False,
    mixed_gap_matching=False,
    max_whitespace_gap=3,
)
engine = KoguardEngine(config=config)
```

기본 설정은 사전 단어의 글자 사이에 들어간 짧은 공백과 탭을 허용하며, 공백과 설정된
`obfuscation_separators`를 함께 섞은 `시 * 발`도 탐지합니다. 각 공백 구간은
`max_whitespace_gap` 이하이어야 하며 줄바꿈은 허용하지 않습니다. 또한 매치 양끝이 영숫자
토큰 중간이면 후보를 버리므로 `시 발`, `시 * 발`, `개 새끼`는 탐지하지만 `시 발표`,
`시 * 발표`, `개 새끼손가락`은 탐지하지 않습니다.

결과의 `matched_text`, `start`, `end`에는 우회 문자를 포함한 원문 구간이 그대로 보존됩니다.
공백·탭만 사용한 결과의 `method`는 `MatchMethod.WHITESPACE`, 공백과 구분자를 모두 사용한
결과는 `MatchMethod.MIXED`입니다.

Whitespace와 Mixed 매칭에서는 Whitelist의 우회 형태를 별도로 확장하지 않습니다. 예를 들어
Whitelist에 `시발 자동차`가 있어도 입력 `시 발 자동차`와 `시 * 발 자동차`의 욕설 구간은
탐지합니다. Whitelist는 입력에 실제로 겹치는 기존 정규화 view의 구간만 보호합니다.

초성 표현 탐지도 기본으로 활성화됩니다. 초성 인덱스의 오탐 가능성이나 추가 메모리 비용을
피하려면 `EngineConfig(choseong_matching=False)`로 끌 수 있습니다.

```python
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["시발", "씨밤", "개새끼"],
    include_defaults=False,
)
engine = KoguardEngine(dictionary=dictionary)

assert engine.check("ㅅㅂ").matched_word == "시발"
assert engine.check("ㅆㅂ").matched_word == "씨밤"
assert engine.check("ㄱㅅㄲ").matched_word == "개새끼"
```

초성 index는 두 글자 이상의 완성형 한글 blacklist 항목에서만 파생합니다. 입력에서는
`ㅅㅂ`처럼 연속된 호환 자모 또는 동등한 현대 초성 자모 토큰만 비교하고, `수박` 같은 일반
한글 문장을 초성으로 변환하지 않습니다. 또한 `ㄱㅅㅂ`, `ㅅㅂㄹ`, `3ㅅㅂ`처럼 더 긴 영숫자
토큰의 일부는 버립니다. 공백·구분자로 나뉜 `ㅅ ㅂ`, `ㅅ*ㅂ`은 현재 초성 단계의 범위가
아닙니다.

여러 blacklist 항목이 같은 초성으로 충돌하면 길이 내림차순·사전순으로 정렬된 첫 항목을
결과의 canonical `term`으로 사용합니다. 특정 초성을 허용하려면 Whitelist에 `ㅅㅂ`처럼
초성 자체를 명시해야 합니다. 탐지 결과의 `method`는 `MatchMethod.CHOSEONG`입니다.

## 개발 환경

Python 3.11.9와 [uv](https://docs.astral.sh/uv/)를 사용합니다.

```powershell
uv sync
uv run python -c "import koguard; print(koguard.__version__)"
```

## 개발 명령

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

## 성능 기준선

저장소 루트에서 다음 명령을 실행하면 고정 corpus의 p50·p95 지연 시간, 처리량, cold start,
steady-state peak memory를 JSON으로 기록합니다.

```powershell
uv run python -m benchmarks.engine_benchmark `
  --iterations 100 `
  --warmups 10 `
  --output benchmarks/results/local.json
```

측정 항목과 결과 해석은 [`benchmarks/README.md`](benchmarks/README.md)를 참고합니다.

## AI 개발 하네스

Koguard는 [Everything Claude Code(ECC)](https://github.com/affaan-m/ECC)의 계획, TDD,
검증, 전문 역할 분리 패턴을 프로젝트 로컬 Codex 설정으로 적용합니다.

- 저장소 규칙: [`AGENTS.md`](AGENTS.md)
- Codex 탐색 지도: [`docs/CODEX-NAVIGATION-GUIDE.md`](docs/CODEX-NAVIGATION-GUIDE.md)
- 개발 워크플로: [`docs/development-workflow.md`](docs/development-workflow.md)
- 코드 리뷰 기준: [`docs/code-review.md`](docs/code-review.md)
- DAILY/LIBRARY 분류: [`docs/ecc-install-plan.md`](docs/ecc-install-plan.md)

전역 모델, 알림, MCP 서버, 자격 증명 설정은 변경하지 않습니다.
