# STORY-005: medium HTML Report Generator and Full Assembly

**Index**: 5
**Complexity**: medium
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-003, STORY-004

## Context
This is the capstone story that completes the tool. It implements the HTML generator (summary table, interactive controls, and the Chart.js line chart with client-side toggle/filter logic), wires all components together in `main()`, and writes the finished report to disk. After this story the tool is fully functional end-to-end.

## Acceptance Criteria

### Summary table
- [ ] The generated HTML contains an HTML `<table>` with a header row: Agent | Input Tokens | Output Tokens | Cache Read Tokens | Cache Write Tokens | Total Cost (USD).
- [ ] Each agent appears as a data row with its per-agent totals; a final **Total** row shows the grand total.
- [ ] Token counts are formatted with thousands separators (e.g. `1,234,567`).
- [ ] Cost values are formatted to 6 decimal places (e.g. `0.001234`).

### Controls
- [ ] The HTML contains a toggle button labelled to indicate switching between "Token Counts" and "Cost USD" views.
- [ ] The HTML contains two `<input type="datetime-local">` elements (From / To) and a Reset button.

### Chart
- [ ] The HTML embeds Chart.js inline inside a `<script>` tag (the bundle obtained from `fetch_chartjs()`).
- [ ] The Chart.js initialisation script creates a line chart on a `<canvas>` element.
- [ ] **Token Counts view** (default): one dataset (line) per `(agent, token_type)` combination; token types are `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`; dataset labels follow the pattern `"<agent> · <type>"`.
- [ ] **Cost USD view**: one dataset per agent; dataset labels follow the pattern `"<agent> · cost_usd"`.
- [ ] All chart data is embedded as a JSON literal in a `<script>` block; no network requests are made after the file is generated.
- [ ] Toggling the button swaps the datasets, updates the Y-axis label ("Token Count" ↔ "Cost (USD)"), and updates the chart title.
- [ ] Changing either date picker filters the visible X-axis labels and corresponding data points to the selected range; when both pickers are empty all data is shown.
- [ ] The Reset button clears both date pickers and restores the full dataset.

### Full assembly and CLI
- [ ] `main()` calls: parse args → load records → aggregate → fetch Chart.js → generate HTML → write file → print output path to stdout.
- [ ] The output file is named `token-report_YYYY-MM-DD_HH-MM-SS.html` (datetime at script run time, underscores not colons).
- [ ] The file is written to the current working directory.
- [ ] `python workspace/token_report.py --tokens-dir <valid-dir>` exits 0 and prints the path of the generated file.
- [ ] `ruff check workspace/` passes with no errors.
- [ ] `pytest workspace/tests/ -v` passes with no failures.

### HTML generator tests (`tests/test_html_generator.py`)
- [ ] At least one test verifies the summary table output contains the correct agent name, a formatted token count, and a 6-decimal-place cost value.
- [ ] At least one test verifies the HTML output contains the Chart.js bundle string.
- [ ] At least one test verifies the embedded JSON data contains the correct dataset labels for both token-count and cost views.

## Implementation Hints
- **HTML generation**: use f-strings and string concatenation — no Jinja2 (stdlib only per design).
- **Data embedding**: use `json.dumps(data, ensure_ascii=False)` to serialise chart data; assign to a `const` in the `<script>` block.
- **Client-side filtering**: the embedded JSON should contain the full unfiltered minute-bucket list; the JS `filterAndRender()` function slices it at render time based on the date-picker values parsed via `new Date(value)`.
- **Chart.js initialisation pattern**:
  ```js
  const chart = new Chart(ctx, { type: 'line', data: {...}, options: {...} });
  ```
  Store the chart instance in a variable so it can be destroyed and re-created on toggle/filter (call `chart.destroy()` before re-creating).
- **Toggle state**: keep a JS boolean `let showCost = false;` and flip it on button click.
- **Date filtering**: compare minute-bucket strings lexicographically (ISO-8601 strings sort correctly as strings).
- **Thousands separator**: `f"{n:,}"` in Python produces the comma-separated format.
- **Cost formatting**: `f"{cost:.6f}"`.
- **`from __future__ import annotations`** must be at the top of `token_report.py` for 3.8 compat with lowercase generics.
- Tests can call `generate_html(minute_buckets, agent_totals, grand_total, chartjs_source)` directly without running the CLI, so keep this as a named function with clear parameters.

## Test Requirements
- Running `python workspace/token_report.py --tokens-dir <dir>` against a directory containing at least two JSONL files should produce an HTML file in the current directory whose name matches `token-report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}.html`, and the tool should print that filename to stdout.
- Opening the generated HTML file and inspecting its text content should reveal: (a) a `<table>` element, (b) both agent names as row labels, (c) a `<canvas>` element, (d) the Chart.js UMD bundle embedded inline, and (e) a JSON literal containing dataset labels in the `"<agent> · <type>"` format.
- Running the tool against a directory with no `.jsonl` files should exit with code 1 and produce no HTML file.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
