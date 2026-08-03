# Koguard Development Workflow

Koguard applies the repeatable planning, TDD, and verification patterns from Everything Claude Code (ECC) to Python library development.

## 1. Work classification

- For documentation typos or obvious single changes, work directly, but do not skip relevant verification.
- For changes that affect public APIs, detection rules, normalization, dictionary loading, or performance, document the impact scope and completion criteria before implementation.
- For external packages, APIs, and datasets, verify the official documentation and source licenses first.

## 2. TDD loop

### Red

- Express new expected behavior or a bug reproduction as tests.
- Confirm whether the failure is caused by the requirement or by an environment issue.

### Green

- Implement the smallest change that makes the tests pass.
- Cover normal paths together with empty input, maximum length, Unicode, multi-match, and whitelist overlap cases.

### Refactor

- Remove duplication and clarify boundaries.
- Verify that public behavior, match order, spans, and score semantics stay unchanged.

## 3. Verification loop

Run fast checks first, then expand to full validation.

```powershell
uv run pytest tests/test_target.py
uv run ruff check path/to/changed_file.py
uv run ruff format --check .
uv run ruff check .
uv run mypy
uv run pytest
uv build
```

## 4. Self review

Review the git diff against the criteria in [code-review.md](code-review.md), especially around false positives on normal text, span preservation after normalization, whitelist masking of unrelated matches, non-deterministic ordering, and input length bypasses.

## 5. Delivery

The completion report should include:

- User-visible behavioral changes
- Key files and design decisions
- Verification commands and results
- Any remaining limitations or unexecuted checks
