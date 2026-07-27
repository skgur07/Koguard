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

기본 사전은 직접 선별한 Exact Match 표현을 포함하며 기본 Whitelist는 비어 있습니다.
따라서 `시발점`, `병신년`처럼 금칙어를 포함한 복합어도 기본 정책에서는 탐지합니다.
서비스 문맥에서 허용할 표현은 `whitelist` 또는 `whitelist_path`로 명시적으로 주입해야 합니다.

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

## AI 개발 하네스

Koguard는 [Everything Claude Code(ECC)](https://github.com/affaan-m/ECC)의 계획, TDD,
검증, 전문 역할 분리 패턴을 프로젝트 로컬 Codex 설정으로 적용합니다.

- 저장소 규칙: [`AGENTS.md`](AGENTS.md)
- Codex 탐색 지도: [`docs/CODEX-NAVIGATION-GUIDE.md`](docs/CODEX-NAVIGATION-GUIDE.md)
- 개발 워크플로: [`docs/development-workflow.md`](docs/development-workflow.md)
- 코드 리뷰 기준: [`docs/code-review.md`](docs/code-review.md)
- DAILY/LIBRARY 분류: [`docs/ecc-install-plan.md`](docs/ecc-install-plan.md)

전역 모델, 알림, MCP 서버, 자격 증명 설정은 변경하지 않습니다.
