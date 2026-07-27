# Koguard

한국어 욕설·비속어 탐지를 위한 경량 Python 라이브러리입니다.

현재 v0.1에서는 기본 사전 기반 Exact Match와 구간 단위 Whitelist 처리를 제공합니다.

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
