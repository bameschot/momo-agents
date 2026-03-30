# STORY-001: easy Project Scaffold

**Index**: 1
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: none

## Context
Before any implementation code can be written or tested, the project needs a
`pyproject.toml` that declares dev-only dependencies (`pytest`, `pytest-cov`,
`ruff`) and the test directory skeleton (`tests/__init__.py`,
`tests/conftest.py`). Everything else in the pipeline depends on this
foundation existing.

## Acceptance Criteria
- [ ] `workspace/pyproject.toml` exists and declares the project as
  `token-report` (or similar), with `pytest`, `pytest-cov`, and `ruff` listed
  under an optional `[dev]` extras group.
- [ ] Running `pip install -e ".[dev]"` from `workspace/` completes without
  error and makes `pytest` and `ruff` available on `PATH`.
- [ ] `workspace/tests/__init__.py` exists (may be empty).
- [ ] `workspace/tests/conftest.py` exists and defines at least one shared
  fixture: a `tmp_tokens_dir` fixture that creates a temporary directory,
  writes one or more sample `.jsonl` files into it (with valid records matching
  the data model), and returns the `Path` to that directory.
- [ ] Running `pytest` from `workspace/` (with no test files yet) exits 0 with
  "no tests ran" (collection succeeds, nothing fails).

## Implementation Hints
- `pyproject.toml` should use `[build-system]` with `setuptools`; minimum
  Python version `>=3.8`.
- Sample JSONL record for conftest:
  ```json
  {"ts": "2026-03-30T12:55:00Z", "input_tokens": 10, "output_tokens": 20, "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.001}
  ```
  Note: the `agent` field is derived from the filename stem, not stored in the
  record itself.
- The `conftest.py` fixture should write at least two agent files (e.g.
  `designer.jsonl`, `ba.jsonl`) so later tests can verify multi-agent
  aggregation.

## Test Requirements
No behavioural tests required — this story is pure scaffolding. The acceptance
criteria (pip install succeeds, pytest collects without error) serve as
verification.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
