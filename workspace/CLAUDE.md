# Token Report — Coding Agent Guide

## Project Overview

`token_report.py` is a **stdlib-only** Python CLI tool that reads per-agent token usage logs from `.sentinels/tokens/*.jsonl`, aggregates them by minute bucket, and generates a self-contained single-page HTML report (with an inline Chart.js bundle).

No third-party Python packages are used at runtime. The only dev dependencies are for testing and linting.

---

## Environment Requirements

- **Python 3.8+** (no conda, no venv required — stdlib only at runtime)
- Dev tools are managed via `pyproject.toml` and can be installed with:

```bash
pip install --quiet ".[dev]"
```

Or, if you prefer a clean virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Commands

### Run the tool

```bash
python workspace/token_report.py
# with a custom tokens directory:
python workspace/token_report.py --tokens-dir /path/to/.sentinels/tokens
```

The generated report is written to the **current working directory** as `token-report_YYYY-MM-DD_HH-MM-SS.html`.

### Run tests

```bash
pytest workspace/tests/ -v
```

### Run linter

```bash
ruff check workspace/
```

### Run formatter (check only)

```bash
ruff format --check workspace/
```

### Apply formatter

```bash
ruff format workspace/
```

---

## Project Structure

```
workspace/
├── CLAUDE.md                  # This file
├── pyproject.toml             # Project metadata + dev dependencies
├── token_report.py            # CLI entry point — the entire tool lives here
├── .chartjs_cache/            # Auto-created cache for the Chart.js UMD bundle
└── tests/
    ├── __init__.py
    ├── test_data_loader.py    # Tests for the data loading / JSONL parsing
    ├── test_aggregator.py     # Tests for the minute-bucket aggregation logic
    └── test_html_generator.py # Tests for the HTML/table/chart output
```

---

## Conventions

- **Single-file tool**: all production code lives in `workspace/token_report.py`. Do **not** split it into a package unless explicitly instructed.
- **No third-party runtime imports**: only `json`, `argparse`, `datetime`, `pathlib`, `collections`, `urllib.request`, and other stdlib modules are allowed in `token_report.py`.
- **Python 3.8 compatibility**: avoid walrus operator (`:=`) use in contexts that need 3.8, f-string `=` specifiers, or `match` statements.
- **Typing**: use type hints (`from __future__ import annotations` for 3.8 forward compat where needed). Prefer `dict`, `list`, `tuple` lowercase generics inside `from __future__ import annotations` blocks; outside them use `Dict`, `List` from `typing`.
- **Tests**: each major internal function should have at least one test. Use `pytest` and plain `assert` statements — no unittest-style classes needed.
- **Chart.js cache**: the tool downloads Chart.js UMD min from the official CDN (`https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js`) on first run and caches it at `workspace/.chartjs_cache/chart.umd.min.js`. Subsequent runs use the cache without a network request.
- **Exit codes**: exit `0` on success, `1` on fatal errors (missing tokens dir, no `.jsonl` files found).
- **Output filename format**: `token-report_YYYY-MM-DD_HH-MM-SS.html` — underscores, not colons, for cross-platform safety.

---

## Key Interfaces (from design)

### CLI

```
python workspace/token_report.py [--tokens-dir <path>]
```

### Raw record shape (parsed from each JSONL line)

```python
{
    "ts": "2026-03-30T12:55:40Z",   # ISO-8601 UTC string
    "agent": "designer",             # derived from filename stem
    "input_tokens": 3,
    "output_tokens": 154,
    "cache_read_tokens": 10120,
    "cache_write_tokens": 0,
    "cost_usd": 0.0,
}
```

### Aggregated minute-bucket shape

```python
{
    "minute": "2026-03-30T12:55:00Z",
    "agent": "designer",
    "input_tokens": 3,
    "output_tokens": 154,
    "cache_read_tokens": 10120,
    "cache_write_tokens": 0,
    "cost_usd": 0.0,
}
```

### Summary table columns

| Agent | Input Tokens | Output Tokens | Cache Read Tokens | Cache Write Tokens | Total Cost (USD) |

- Numbers: thousands separators (`,`)
- Cost: 6 decimal places (e.g. `0.001234`)
- Last row: **Total** grand-total across all agents
