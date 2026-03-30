# STORY-002: easy token_report.py Skeleton and parse_args()

**Index**: 2
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-001

## Context
All logic lives in a single file `workspace/token_report.py`. This story
creates that file with the full function signature set stubbed out (so later
stories can import and fill in individual functions without structural
conflicts), and fully implements `parse_args()`. The `main()` entry guard is
also put in place so the file is importable in tests without triggering I/O.

## Acceptance Criteria
- [ ] `workspace/token_report.py` exists.
- [ ] The file defines exactly these top-level functions (bodies may be stubs
  returning `None` or raising `NotImplementedError` except where noted):
  - `parse_args()` — **fully implemented** (see below)
  - `load_records(tokens_dir)` — stub
  - `aggregate(records)` — stub
  - `fetch_chartjs(cache_dir)` — stub
  - `build_html(agg, chartjs_src)` — stub
  - `main()` — stub
- [ ] `parse_args()` uses `argparse` and accepts one optional argument
  `--tokens-dir` with default value `.sentinels/tokens`.
- [ ] `parse_args()` returns an `argparse.Namespace` with a `tokens_dir`
  attribute (note: `argparse` converts `--tokens-dir` to `tokens_dir`).
- [ ] The file ends with `if __name__ == "__main__": main()` and contains no
  side effects at module import time.
- [ ] `ruff check workspace/token_report.py` passes with no errors.
- [ ] The file imports only from the Python stdlib (`argparse`, `pathlib`,
  `json`, `sys`, `datetime`, `collections`, `urllib.request` — no third-party
  packages).

## Implementation Hints
- Use `typing` imports (`List`, `Dict`, `Optional`) for 3.8 compatibility;
  avoid `list[dict]` PEP 585 syntax in annotations.
- Stub bodies should be `raise NotImplementedError` so tests that accidentally
  call them fail loudly rather than silently returning `None`.
- All imports should be at the top of the file so `ruff` is satisfied.

## Test Requirements
- Importing `token_report` in a test must not raise any exception and must not
  produce any stdout/stderr output.
- `parse_args()` called with `[]` must return a namespace where
  `args.tokens_dir == ".sentinels/tokens"`.
- `parse_args()` called with `["--tokens-dir", "/tmp/t"]` must return a
  namespace where `args.tokens_dir == "/tmp/t"`.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
