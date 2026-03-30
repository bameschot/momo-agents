# Design: Token Usage Report Generator

## Overview

A command-line Python tool (`workspace/token_report.py`) that reads per-agent token usage logs from `.sentinels/tokens/*.jsonl`, aggregates the data, and produces a self-contained single-page HTML report. The report includes:

1. A **summary table** showing total token counts per type and total cost per agent, plus a grand-total row.
2. A **single interactive Chart.js line chart** that can be toggled between a *token counts* view and a *cost USD* view, with client-side date/time range filtering via HTML date pickers.

The tool has no third-party Python dependencies (pure stdlib). Chart.js is bundled inline in the generated HTML so the report works fully offline.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Language | Python 3.x (stdlib only) |
| Charting | Chart.js (latest stable, source embedded inline in HTML) |
| Templating | Python f-strings / string concatenation (no Jinja2) |
| Data format | JSONL (one JSON object per line) |
| Output | Single self-contained `.html` file |

---

## Project Structure

```
workspace/
└── token_report.py          # The tool

.sentinels/
└── tokens/
    ├── designer.jsonl       # One file per agent (auto-discovered)
    ├── ba.jsonl
    ├── orchestrator.jsonl
    └── ...

token-report_YYYY-MM-DD_HH-MM-SS.html   # Output (written to CWD)
```

---

## Components

### 1. CLI Entry Point
- Parses optional arguments:
  - `--tokens-dir <path>` — path to the `.sentinels/tokens/` directory (default: `.sentinels/tokens/` relative to CWD).
  - No other flags; date filtering is done interactively inside the HTML.
- Resolves the output filename as `token-report_YYYY-MM-DD_HH-MM-SS.html` (datetime = script run time) and writes to CWD.

### 2. Data Loader
- Walks `<tokens-dir>/` and collects every `*.jsonl` file.
- Each file represents one agent; the agent name is derived from the filename stem (e.g. `designer.jsonl` → `"designer"`).
- Parses each line as a JSON object. Skips blank lines and lines that fail to parse (with a stderr warning).
- Produces a list of records:
  ```python
  {
    "ts": "2026-03-30T12:55:40Z",   # ISO-8601 UTC string
    "agent": "designer",
    "input_tokens": 3,
    "output_tokens": 154,
    "cache_read_tokens": 10120,
    "cache_write_tokens": 0,
    "cost_usd": 0.0
  }
  ```

### 3. Aggregator
- Groups records by **(agent, minute bucket)** where the minute bucket is the timestamp truncated to `YYYY-MM-DDTHH:MM:00Z`.
- For each bucket, sums: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`.
- Also computes **per-agent totals** (across all time) for the summary table:
  - Total `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`
- Computes a **grand-total row** by summing all agents.

### 4. HTML / Chart Generator
Produces a single HTML string containing:

#### 4a. Summary Table
An HTML `<table>` with columns:

| Agent | Input Tokens | Output Tokens | Cache Read Tokens | Cache Write Tokens | Total Cost (USD) |
|---|---|---|---|---|---|
| designer | … | … | … | … | … |
| ba | … | … | … | … | … |
| **Total** | … | … | … | … | … |

Numbers are formatted with thousands separators; cost is formatted to 6 decimal places.

#### 4b. Controls
- **Toggle button**: `[ Token Counts | Cost USD ]` — switches the chart's Y-axis and dataset.
- **From datetime picker** (`<input type="datetime-local">`) and **To datetime picker** — filter the visible time range.
- **Reset** button to clear date filters.

#### 4c. Line Chart (Chart.js)
- One `<canvas>` element.
- **Token Counts view**: one line per `(agent, token_type)` combination. Token types: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`. Series label format: `"<agent> · <type>"` (e.g. `"designer · input_tokens"`).
- **Cost USD view**: one line per agent. Series label: `"<agent> · cost_usd"`.
- X-axis: minute-bucket timestamps (string labels).
- Y-axis: token count (integer) or cost USD (float), labelled accordingly.
- Chart title updates when view is toggled.
- All data is embedded as a JSON literal in a `<script>` block; filtering and toggling are pure client-side JS — no network requests after the file is generated.

#### 4d. Client-side JS logic
- On page load: initialise Chart.js with the *token counts* view as default.
- Toggle button: swap dataset arrays, update Y-axis label and chart title, re-render.
- Date pickers: on change, filter the embedded data to only include minute buckets within `[from, to]`, re-render. When both pickers are empty, all data is shown.
- Reset button: clears both pickers and restores full dataset.

#### 4e. Chart.js inline bundle
- The Chart.js UMD source is downloaded at design/build time and embedded verbatim inside a `<script>` tag, making the HTML fully self-contained.
- At tool runtime the script checks if a local cached copy exists (e.g. `workspace/.chartjs_cache/chart.umd.min.js`); if not, it downloads it from the official CDN using `urllib.request` and caches it for subsequent runs.

---

## Data Model

### Raw record (from JSONL)
| Field | Type | Description |
|---|---|---|
| `ts` | string (ISO-8601) | Timestamp of the API call |
| `agent` | string | Agent name (derived from filename) |
| `input_tokens` | int | Prompt/input tokens consumed |
| `output_tokens` | int | Completion/output tokens consumed |
| `cache_read_tokens` | int | Tokens served from prompt cache |
| `cache_write_tokens` | int | Tokens written to prompt cache |
| `cost_usd` | float | Cost for this call in USD |

### Aggregated minute bucket
| Field | Type | Description |
|---|---|---|
| `minute` | string (`YYYY-MM-DDTHH:MM:00Z`) | Minute bucket |
| `agent` | string | Agent name |
| `input_tokens` | int | Sum over the minute |
| `output_tokens` | int | Sum over the minute |
| `cache_read_tokens` | int | Sum over the minute |
| `cache_write_tokens` | int | Sum over the minute |
| `cost_usd` | float | Sum over the minute |

---

## API / Interfaces

### CLI
```
python workspace/token_report.py [--tokens-dir <path>]
```

| Flag | Default | Description |
|---|---|---|
| `--tokens-dir` | `.sentinels/tokens` (relative to CWD) | Path to directory containing `*.jsonl` files |

**Output**: `./token-report_YYYY-MM-DD_HH-MM-SS.html` in CWD.
**Stdout**: prints the path of the generated file on success.
**Stderr**: warnings for unparseable lines; error + exit code 1 if tokens dir not found or no `.jsonl` files discovered.

---

## Non-Functional Requirements

| Requirement | Detail |
|---|---|
| **Self-contained output** | The HTML file must render correctly with no internet connection after generation (Chart.js embedded inline) |
| **No pip dependencies** | Tool uses Python stdlib only (`json`, `argparse`, `datetime`, `pathlib`, `collections`, `urllib.request`) |
| **Filename safety** | Output filename uses format `token-report_YYYY-MM-DD_HH-MM-SS.html` (no colons; safe on macOS, Linux, Windows) |
| **Graceful degradation** | Unparseable JSONL lines are skipped with a warning; tool still produces a report from valid data |
| **Performance** | Designed for small-to-medium log files (thousands of lines per agent); no streaming required |
| **Portability** | Python 3.8+ compatible; no OS-specific APIs |

---

## Open Questions

_None — all requirements have been agreed with the user._
