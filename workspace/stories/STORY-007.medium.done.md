# STORY-007: medium build_html() — Chart.js Data Embedding and Chart Initialisation

**Index**: 7
**Complexity**: medium
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-006

## Context
With the summary table in place (STORY-006), this story extends `build_html()` to
embed all time-series data as a JSON literal and initialise a Chart.js line chart
with two pre-computed dataset arrays: one for token counts (four series per agent)
and one for cost USD (one series per agent). The toggle button and date-filter
controls are added as static HTML here; their interactive JS behaviour is wired up
in STORY-008.

## Acceptance Criteria
- [ ] `build_html()` now embeds `chartjs_src` verbatim inside a `<script>` tag
  (placed before the closing `</body>` tag) so Chart.js is available client-side
  without any network request.
- [ ] The HTML contains a `<canvas id="tokenChart">` element inside
  `#chart-container`.
- [ ] The HTML contains the interactive controls:
  - A toggle button with `id="toggleBtn"` and initial label `"Switch to Cost USD"`.
  - A **From** `<input type="datetime-local" id="fromPicker">`.
  - A **To** `<input type="datetime-local" id="toPicker">`.
  - A **Reset** button with `id="resetBtn"`.
- [ ] All minute-bucket time-series data is serialised as a single JSON literal
  assigned to a JS variable `const RAW_DATA = <json>;` in a `<script>` block.
  The JSON must contain enough structure for client-side filtering and series
  construction (at minimum: the list of minute labels and per-series values).
- [ ] On page load, Chart.js is initialised with a `line` chart using the
  **token counts** view as the default:
  - One line per `(agent, token_type)` combination (four token types ×
    number of agents).
  - Series label format: `"<agent> · <token_type>"`.
  - Chart title: `"Token Usage Over Time"`.
  - Y-axis label: `"Tokens"`.
- [ ] The chart renders correctly in a browser when the HTML file is opened
  (no JS console errors from missing data or Chart.js API misuse).
- [ ] `ruff check workspace/token_report.py` passes after this change.

## Implementation Hints
- Serialise `RAW_DATA` with `json.dumps(...)` inside the f-string.
  Structure suggestion:
  ```json
  {
    "labels": ["2026-03-30T12:00:00Z", ...],
    "token_series": [
      {"label": "designer · input_tokens", "data": [120, ...]},
      ...
    ],
    "cost_series": [
      {"label": "designer · cost_usd", "data": [0.001234, ...]},
      ...
    ]
  }
  ```
  Building this in Python before `json.dumps` keeps the logic clean.
- Labels are the **union** of all minute buckets across all agents, sorted
  chronologically. For agents that have no record in a given bucket, emit `0`
  (not `null`) so Chart.js draws a continuous line.
- Use `Chart.js` v3/v4 constructor API:
  `new Chart(ctx, { type: 'line', data: { labels, datasets }, options: { ... } })`.
- Assign the chart instance to `window.chart` so STORY-008 can call
  `window.chart.update()`.
- Keep `chartjs_src` embedding as `<script>${chartjs_src}</script>` — do not URL-
  reference it.

## Test Requirements
- The HTML returned by `build_html()` contains the string `const RAW_DATA =`.
- The HTML contains `<canvas id="tokenChart">`.
- The embedded JSON is valid (parse it back with `json.loads()` and verify it has
  keys `labels`, `token_series`, `cost_series`).
- A `token_series` entry exists for every `(agent, token_type)` combination
  present in the aggregation data.
- A `cost_series` entry exists for every agent.
- For an agent with no records in a particular minute, the corresponding data
  point is `0`.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
