# Token Report Generator — Build & Test Guide

## Project Overview

A Python CLI tool that reads token usage logs from `.sentinels/tokens/*.jsonl`, aggregates the data, and generates a self-contained interactive HTML report with Chart.js visualizations.

**Technology Stack:**
- Language: Python 3.8+
- Dependencies: stdlib only (json, argparse, datetime, pathlib, collections, urllib.request)
- Charting: Chart.js (embedded inline in generated HTML)
- Testing: pytest
- Linting: ruff, pycodestyle (or similar lightweight linters compatible with stdlib-only projects)

---

## Installation & Setup

No package installation required — this project uses Python stdlib only.

To set up the development environment:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

For development (linting and testing):

```bash
pip install pytest ruff
```

---

## Running the Tool

```bash
python token_report.py [--tokens-dir <path>]
```

**Arguments:**
- `--tokens-dir <path>`: path to directory containing `*.jsonl` files (default: `.sentinels/tokens` relative to CWD)

**Output:**
- Generates `token-report_YYYY-MM-DD_HH-MM-SS.html` in the current working directory
- Prints the path to the generated report on stdout
- Warnings or errors (if any) are printed to stderr

**Example:**

```bash
python token_report.py --tokens-dir .sentinels/tokens
# Output: token-report_2026-03-31_14-30-45.html
```

---

## Testing

Run the test suite with pytest:

```bash
pytest
```

Or with verbose output:

```bash
pytest -v
```

**Test location:** `tests/` directory
**Test discovery:** pytest will automatically discover `test_*.py` files

---

## Linting & Formatting

**Run linting checks:**

```bash
ruff check token_report.py tests/
```

**Auto-format code (if using ruff format):**

```bash
ruff format token_report.py tests/
```

Or use standard Python formatting tools (black, autopep8, etc.):

```bash
black token_report.py tests/
# or
autopep8 --in-place token_report.py tests/
```

**PEP 8 compliance check:**

```bash
pycodestyle token_report.py tests/
```

---

## Environment Variables

None required. The tool operates entirely on the filesystem.

---

## Project Conventions

1. **Code style:** PEP 8; max line length 100 characters
2. **Docstrings:** All functions and modules must have docstrings explaining purpose, parameters, and return values
3. **Error handling:**
   - Invalid JSON lines in JSONL files: log a warning to stderr and skip the line
   - Missing tokens directory: log an error to stderr and exit with code 1
   - No `.jsonl` files found: log an error to stderr and exit with code 1
4. **Data model:** Follow the structures defined in the design document (raw records, aggregated minute buckets)
5. **HTML output:** Self-contained; Chart.js must be embedded inline (cached from CDN on first run, or provided locally)
6. **Testing:** Unit tests for each component (loader, aggregator, HTML generator); integration test for end-to-end execution
7. **Output format:** `token-report_YYYY-MM-DD_HH-MM-SS.html` (no colons in timestamp for Windows compatibility)

---

## Quick Reference

| Task | Command |
|---|---|
| Run tool | `python token_report.py [--tokens-dir <path>]` |
| Run tests | `pytest` |
| Lint code | `ruff check .` |
| Format code | `ruff format .` |
| Install dev dependencies | `pip install pytest ruff` |
| Enter virtual environment | `source .venv/bin/activate` |
| Exit virtual environment | `deactivate` |

---

## Notes

- **No external dependencies:** This tool uses only Python stdlib, making it portable and lightweight.
- **Chart.js caching:** The tool downloads Chart.js from the CDN and caches it locally at `./.chartjs_cache/chart.umd.min.js` on first run. Subsequent runs use the cached version.
- **Offline support:** Once the HTML report is generated, it requires no internet connection to view or interact with.
- **File safety:** Output filename uses underscores instead of colons to ensure compatibility with Windows filesystems.
