# Token Report — Coding Agent Guide

## Project Overview

A pure-stdlib Python 3 CLI tool (`token_report.py`) that reads per-agent token
usage logs from `.sentinels/tokens/*.jsonl`, aggregates the data, and produces
a self-contained single-page HTML report with an interactive Chart.js chart.

---

## Environment Requirements

- **Python**: 3.8 or later (`python3 --version`)
- **No runtime pip dependencies** — the tool itself uses Python stdlib only.
- **Dev dependencies** (testing & linting only): installed via `pip install -e ".[dev]"`.

---

## Setup

```bash
# From the workspace/ directory:
pip install -e ".[dev]"
```

This installs `pytest`, `pytest-cov`, and `ruff` as dev tools.

---

## Running the Tool

```bash
# From the project root (momo-agents/):
python workspace/token_report.py

# With an explicit tokens directory:
python workspace/token_report.py --tokens-dir .sentinels/tokens

# From workspace/ itself:
python token_report.py --tokens-dir ../.sentinels/tokens
```

Output file: `./token-report_YYYY-MM-DD_HH-MM-SS.html` (written to CWD).

---

## Running Tests

```bash
# From workspace/ directory:
pytest

# With coverage:
pytest --cov=token_report --cov-report=term-missing

# Run a specific test file:
pytest tests/test_data_loader.py -v
```

---

## Linting & Formatting

```bash
# Check for lint issues:
ruff check .

# Auto-fix lint issues:
ruff check --fix .

# Format code:
ruff format .

# Check formatting without modifying:
ruff format --check .
```

---

## Project Layout

```
workspace/
├── token_report.py           # Main CLI entry point (the deliverable)
├── pyproject.toml            # Project metadata + dev dependencies
├── .chartjs_cache/           # Auto-created at runtime; cached Chart.js bundle
│   └── chart.umd.min.js      # Downloaded once from CDN, reused on subsequent runs
└── tests/
    ├── __init__.py
    ├── conftest.py            # Shared pytest fixtures (sample JSONL data, tmp dirs)
    ├── test_cli.py            # CLI argument parsing & end-to-end invocation
    ├── test_data_loader.py    # load_records(): JSONL parsing, error handling
    ├── test_aggregator.py     # aggregate(): minute-bucket grouping & per-agent totals
    └── test_html_generator.py # build_html(): summary table & Chart.js data embedding
```

---

## Module Structure of `token_report.py`

The entire tool lives in **one file** (`token_report.py`). Implement it as a
set of clearly separated functions following this internal structure:

| Function | Responsibility |
|---|---|
| `parse_args()` | `argparse` setup; returns `Namespace` |
| `load_records(tokens_dir: Path) -> list[dict]` | Walk `*.jsonl`, parse lines, return records |
| `aggregate(records: list[dict]) -> dict` | Return `{"buckets": [...], "agent_totals": {...}, "grand_total": {...}}` |
| `fetch_chartjs(cache_dir: Path) -> str` | Return Chart.js UMD source (from cache or CDN) |
| `build_html(agg: dict, chartjs_src: str) -> str` | Return full HTML string |
| `main()` | Orchestrates everything; writes the HTML file |

---

## Key Conventions

1. **stdlib only** — never `import` a third-party package inside `token_report.py`.
2. **Python 3.8+ compatibility** — no `match` statements, no `|` union type hints;
   use `Optional[X]` / `Union[X, Y]` from `typing` if needed.
3. **Minute-bucket format**: `YYYY-MM-DDTHH:MM:00Z` (UTC, trailing `:00Z`).
4. **Output filename format**: `token-report_YYYY-MM-DD_HH-MM-SS.html` (no colons —
   safe on macOS, Linux, and Windows).
5. **Thousands separators** for token counts: `f"{n:,}"`.
6. **Cost formatting**: 6 decimal places — `f"{cost:.6f}"`.
7. **Graceful degradation**: unparseable JSONL lines → `sys.stderr` warning, skip.
8. **Exit code 1** if tokens directory not found or no `.jsonl` files discovered.
9. **Chart.js cache path**: `workspace/.chartjs_cache/chart.umd.min.js`
   (relative to the script's own directory).
10. **No side effects at import time** — all logic must be inside functions so
    tests can import individual functions without triggering I/O.

---

## Environment Variables

None required. All paths are passed via CLI flags or derived from the script location.

---

## Chart.js CDN URL

```
https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js
```

The tool uses `urllib.request.urlopen` to fetch this if the cache is missing.
