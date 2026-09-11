# Koguard

Koguard is a lightweight Python library for detecting Korean profanity and abusive language.

The current v0.1 release provides dictionary-based exact match detection and span-based whitelist handling.

## Quick start

```python
from koguard import KoguardEngine

engine = KoguardEngine()
result = engine.check("text to inspect")

print(result.detected)
print(result.matches)
```

You can also provide your own dictionary instead of the bundled defaults.

```python
from koguard import KoguardDictionary, KoguardEngine

dictionary = KoguardDictionary.from_sources(
    blacklist=["banned term"],
    whitelist=["allowed phrase"],
    include_defaults=False,
)
engine = KoguardEngine(dictionary=dictionary)
```

## Development environment

The project uses Python 3.11.9 and uv.

```powershell
uv sync
uv run python -c "import koguard; print(koguard.__version__)"
```

## Development commands

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

## Documentation index

- [Development workflow](docs/development-workflow.md)
- [Code review criteria](docs/code-review.md)
- [Codex navigation guide](docs/CODEX-NAVIGATION-GUIDE.md)
- [Accuracy baseline](docs/accuracy-baseline.md)
- [ECC implementation plan](docs/ecc-install-plan.md)
- [Implementation plan](docs/implementation-plan.md)
- [Benchmark guide](benchmarks/README.md)
