# STORY-008: medium build_html() — Client-Side Toggle and Date-Filter JS

**Index**: 8
**Complexity**: medium
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-007

## Context
The chart canvas and data are already embedded (STORY-007). This story adds the
client-side JavaScript that makes the report interactive: toggling between the
token-counts view and the cost-USD view, filtering the visible time range via the
date pickers, and resetting the filters. All logic is pure JS operating on the
`RAW_DATA` literal already embedded in the page — no network requests.

## Acceptance Criteria
- [ ] **Toggle button** (`#toggleBtn`): clicking it switches the chart between
  two views and updates the button label accordingly:
  - *Token counts* view → datasets from `RAW_DATA.token_series`, Y-axis label
    `"Tokens"`, chart title `"Token Usage Over Time"`, button label
    `"Switch to Cost USD"`.
  - *Cost USD* view → datasets from `RAW_DATA.cost_series`, Y-axis label
    `"Cost (USD)"`, chart title `"Token Cost Over Time"`, button label
    `"Switch to Token Counts"`.
  - After each toggle `window.chart.update()` is called.
- [ ] **Date pickers** (`#fromPicker`, `#toPicker`): when either picker value
  changes, the chart re-renders showing only minute buckets whose timestamp falls
  within `[from, to]` (inclusive). If a picker is empty, that bound is unbounded.
- [ ] **Reset button** (`#resetBtn`): clears both pickers and re-renders the chart
  with all data restored.
- [ ] When both pickers are empty the full dataset (all buckets) is displayed.
- [ ] The current view mode (token counts vs cost USD) is preserved across filter
  changes — filtering does not reset the toggled view.
- [ ] All JS is inline (inside a `<script>` block in the HTML); no external JS
  file references.
- [ ] `ruff check workspace/token_report.py` passes after this change (Python
  linting only — JS is inside a string).

## Implementation Hints
- Store the current view in a JS variable, e.g. `let currentView = 'tokens';`,
  toggled on button click.
- Write a `renderChart(labels, datasets)` JS helper that updates
  `window.chart.data.labels` and `window.chart.data.datasets`, then calls
  `window.chart.update()`. Reuse it from the toggle handler, filter handler, and
  reset handler.
- For filtering, compute `filteredLabels` and `filteredData` by iterating
  `RAW_DATA.labels` and keeping indices where the label string (an ISO-8601
  minute bucket) falls within `[fromPicker.value, toPicker.value]`. The
  `datetime-local` input value is also an ISO-8601-like string (`YYYY-MM-DDTHH:MM`);
  string comparison works for this format.
- Chart title update: use `window.chart.options.plugins.title.text = ...` then
  `window.chart.update()`.
- Y-axis label update: `window.chart.options.scales.y.title.text = ...`.

## Test Requirements
- Open the generated HTML file in a headless browser or simply verify the
  structure: the HTML contains JS functions or event handlers for `toggleBtn`,
  `fromPicker`, `toPicker`, and `resetBtn` (check for their `id` references
  appearing in the `<script>` blocks).
- The HTML contains the string `currentView` (or an equivalent state variable)
  confirming toggle-state tracking is present.
- End-to-end: running `python workspace/token_report.py --tokens-dir <fixtures>`
  produces an HTML file, and opening that file in a browser shows the chart with
  functioning controls (manual verification acceptable for this story).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
