# Codex Repository Navigation Guide

## Quick map

| Path | Ownership area |
| --- | --- |
| src/koguard/__init__.py | Public import surface and version |
| src/koguard/config.py | Input limits and normalization settings |
| src/koguard/models.py | Public result models and invariants |
| src/koguard/engine/engine.py | Detection pipeline assembly and public check() |
| src/koguard/engine/dictionary.py | Dictionary loading, normalization, and deterministic ordering |
| src/koguard/engine/matcher.py | Exact candidates and whitelist span handling |
| src/koguard/engine/normalizer/ | Normalization views and source index mapping |
| src/koguard/data/ | Bundled dictionaries and notices |
| tests/ | Public contracts and regression tests |
| docs/implementation-plan.md | Stepwise product and architecture plan |
| docs/accuracy-baseline.md | Current accuracy baseline |

## Exploration order

1. Start with the public API and relevant tests.
2. Follow the call path from engine.py into matcher, dictionary, and normalizer.
3. Check model invariants and exception contracts.
4. Review corpus and whitelist cases before changing behavior.
5. After implementation, widen verification to the full quality gate.

## Change ownership

- Public API changes should be reviewed together in the initializer, models, docs, and tests.
- Normalization changes should be validated with matcher accuracy and span tests.
- Dictionary changes should be reviewed together with notice files and distribution licensing considerations.
