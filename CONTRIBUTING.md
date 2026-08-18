# Contributing to Koguard

## Development environment

Koguard targets CPython 3.11.9 and uses `uv`.

```powershell
uv sync --all-extras --dev
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

Feature and bug-fix work starts from `dev` on a `feature/*` branch. Use Conventional Commit subjects with a
short Korean description. Add a failing public-behavior test before changing runtime behavior and keep the
branch coverage gate at 90% or higher.

## Data and privacy

Do not commit private service messages, hidden evaluation text, annotation work files, quarantine corpus, API
keys, model weights, or material whose redistribution rights are unclear. A dictionary or corpus proposal must
include a fixed source revision, license evidence, intended public scope, and a policy-aware positive and
hard-negative evaluation. External detector output is a candidate signal, not a gold label.

Packaged dictionary changes must update `evaluation/dictionary-provenance.v1.json`, the data changelog,
relevant tests, and `src/koguard/data/NOTICE.md` together. The offline provenance validator must pass before a
candidate can be promoted.

## Pull requests

Describe the user-visible change, root cause, tests and quality gates, data/license impact, and known limits.
Keep unrelated changes in separate commits. Never weaken a correctness expectation or performance budget only
to make a change pass.
