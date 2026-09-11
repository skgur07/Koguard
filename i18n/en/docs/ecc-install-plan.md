# ECC Project Integration Plan

This document is a selective application of Everything Claude Code (ECC) to Koguard based on repository evidence.

## STACK

- Language and runtime: Python files, CPython 3.11.9
- Package management and build: uv, Hatchling
- Quality tools: Ruff, mypy strict, pytest, pytest-cov
- Product surface: a network-free Korean profanity detection library

## DAILY

| ECC surface | Type | Repository evidence | Applied |
| --- | --- | --- | --- |
| tdd-workflow | skill | tests/ and 90% branch coverage gate | Used for feature and bug-fix work |
| error-handling | skill | public exceptions and input validation tests | Used when failure contracts change |
| verification-loop | skill | Ruff, mypy, pytest, and build commands | Used before completion |
| git-workflow | skill | dev, feature/*, and main branch workflow | Used for branch and commit work |
| agent-self-evaluation | skill | final quality review for multi-file changes | Used for non-trivial work |

## INSTALL PLAN

- Keep AGENTS.md, Codex role definitions, and development/review docs in the repository.
- Do not duplicate ECC skill bodies if the user skill store already provides them.
- Keep project-level sandbox and role configuration minimal and read-only.
