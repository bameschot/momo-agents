# STORY-001: easy Project Scaffold

**Index**: 1
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: none

## Context
Before any other code can be written or tested, the project needs its structural skeleton in place: a `pyproject.toml` that declares the project's metadata and dev dependencies, and the `tests/` package directory with an `__init__.py` so `pytest` can discover tests. Without this scaffold every subsequent story has nowhere to land.

## Acceptance Criteria
- [ ] `workspace/pyproject.toml` exists and declares the project name, a Python `>=3.8` requirement, and a `[project.optional-dependencies] dev` group that includes at least `pytest` and `ruff`.
- [ ] `workspace/tests/__init__.py` exists (may be empty).
- [ ] `pip install --quiet ".[dev]"` (run from inside `workspace/`) succeeds and installs `pytest` and `ruff`.
- [ ] `ruff check workspace/` exits 0 on a clean repository (no source files yet to lint).
- [ ] `pytest workspace/tests/ -v` exits 0 (no tests collected is acceptable at this stage).

## Implementation Hints
- Use `[build-system]` with `setuptools` or `flit_core` — either is fine; choose whichever requires less boilerplate.
- The `[project]` table should set `name = "token-report"` and `requires-python = ">=3.8"`.
- `ruff` configuration can live inline in `pyproject.toml` under `[tool.ruff]`; a minimal config (just `line-length = 100`) is sufficient.
- No `token_report.py` needs to exist yet — that is created in STORY-002.

## Test Requirements
No behavioural tests required — this story is pure project scaffolding with no observable runtime behaviour.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
