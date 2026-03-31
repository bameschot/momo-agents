# STORY-006: medium Interactive Chart and Controls HTML Renderer

**Index**: 6
**Complexity**: medium
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-003

## Context
This story implements the interactive Chart.js section of the report. It produces an HTML fragment containing: a toggle button (Token Counts / Cost USD), two datetime-range pickers, a reset button, a `<canvas>` element, and an inline `<script>` block that embeds all aggregated data as JSON and implements all client-side interactivity. The Chart.js source itself is injected separately by the integration story (STORY-007); this function receives it as a parameter.

## Acceptance Criteria
- [ ] `render_chart_html(buckets: list[dict], chartjs_src: str) -> str` is implemented in `workspace/token_report.py`, replacing the stub from STORY-001.
- [ ] Returns an HTML string containing:
  - A `<script>` tag with `chartjs_src` embedded verbatim (making the output self-contained).
  - A toggle button that switches between "Token Counts" and "Cost USD" views.
  - A "From" `<input type="datetime-local">` and a "To" `<input type="datetime-local">` for date-range filtering.
  - A "Reset" button that clears both pickers and restores the full dataset.
  - A `<canvas id="tokenChart">` element.
  - An inline `<script>` block that embeds the aggregated data as a JSON literal and initialises Chart.js.
- [ ] **Token Counts view**: the chart has one dataset (line) per `(agent, token_type)` combination. Token types are `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`. Dataset labels follow the format `"<agent> · <token_type>"`.
- [ ] **Cost USD view**: one dataset per agent, labelled `"<agent> · cost_usd"`.
- [ ] X-axis labels are the `minute` strings from the buckets (chronological order, deduplicated).
- [ ] Y-axis is labelled "Token Count" in the Token Counts view and "Cost (USD)" in the Cost USD view.
- [ ] Chart title updates when the view is toggled (e.g. "Token Usage Over Time" vs "Cost Over Time").
- [ ] The toggle button switches the active view and re-renders the chart with Chart.js `chart.update()`.
- [ ] Date pickers filter the visible X-axis range: only minute buckets within `[from, to]` are shown; when either picker is empty, that bound is open.
- [ ] The Reset button clears both pickers and restores the full unfiltered dataset.
- [ ] All data filtering and rendering is purely client-side; the HTML file makes no network requests after generation.
- [ ] Function has a docstring.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Embed all chart data as a JSON literal in the `<script>` block:
  ```js
  const RAW_BUCKETS = <json.dumps(buckets)>;
  ```
  From this, derive the two dataset shapes in JS: token-count datasets and cost datasets.
- Use `json.dumps(buckets, default=str)` to serialise the bucket list safely.
- Initialise Chart.js once on `DOMContentLoaded`. Keep a reference to the chart instance in a `let chart` variable so it can be destroyed and recreated (or updated) on toggle/filter.
- For filtering: compare `bucket.minute` string against the picker values (both are ISO-compatible strings — direct string comparison works for `YYYY-MM-DDTHH:MM` format if minute strings have that prefix).
- Destroying and recreating the chart (`chart.destroy(); chart = new Chart(...)`) on each re-render is simpler than mutating datasets in place and avoids Chart.js state bugs.
- Assign distinct colours to agents/series using a fixed palette array in JS to keep the chart readable.
- Keep the JS logic in a single `<script>` block using plain ES6 (no modules, no bundler) for maximum browser compatibility.

## Test Requirements
Create `tests/test_chart_html.py`.

- **Data embedding**: given a known list of buckets (two agents, several minutes), call `render_chart_html(buckets, "/* fake chartjs */")` and assert the returned HTML contains the serialised bucket data (e.g. the `minute` strings appear as JSON literals in the `<script>` block).
- **Series labels**: assert the HTML contains dataset labels for each expected `(agent, token_type)` combination (e.g. `"designer · input_tokens"`) and each agent's cost label (e.g. `"designer · cost_usd"`).
- **Controls present**: assert the HTML contains a toggle button, two `datetime-local` inputs, and a reset button.
- **Canvas present**: assert a `<canvas` element with `id="tokenChart"` is present.
- **Chart.js injection**: assert the literal string `"/* fake chartjs */"` appears in the returned HTML.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
