# STORY-006: medium build_html() — Page Skeleton and Summary Table

**Index**: 6
**Complexity**: medium
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-004

## Context
`build_html()` is responsible for generating the complete HTML report string.
This story implements the first half: the overall page structure (doctype, head,
basic CSS) and the summary table that shows per-agent and grand-total token counts
and costs. At the end of this story `build_html()` returns a valid, viewable HTML
page — without a chart yet (the canvas placeholder and script are added in
STORY-007).

## Acceptance Criteria
- [ ] `build_html(agg: dict, chartjs_src: str) -> str` is partially implemented:
  it returns a valid HTML5 document string (starts with `<!DOCTYPE html>`).
- [ ] The HTML `<head>` sets `<meta charset="utf-8">` and a descriptive `<title>`
  (e.g. `"Token Usage Report"`).
- [ ] The page contains a summary `<table>` with six columns:
  **Agent**, **Input Tokens**, **Output Tokens**, **Cache Read Tokens**,
  **Cache Write Tokens**, **Total Cost (USD)**.
- [ ] Each agent in `agg["agent_totals"]` appears as one `<tr>` in the table body;
  agents are listed in alphabetical order.
- [ ] The table contains a **Grand Total** `<tfoot>` row populated from
  `agg["grand_total"]`.
- [ ] Token counts are formatted with thousands separators (`f"{n:,}"`).
- [ ] Cost values are formatted to 6 decimal places (`f"{cost:.6f}"`).
- [ ] The function includes a `<div id="chart-container">` placeholder where the
  chart will be inserted in STORY-007 (can be empty for now).
- [ ] `chartjs_src` is accepted as a parameter but not yet used (will be embedded
  in STORY-007).
- [ ] `ruff check workspace/token_report.py` passes after this change.

## Implementation Hints
- Build the HTML as a series of f-string segments concatenated with `+` or stored
  in a list joined at the end; avoid Jinja2 or any templating library.
- Generate table rows using a list comprehension or loop over
  `sorted(agg["agent_totals"].items())`.
- Inline minimal CSS (e.g. `font-family: sans-serif; border-collapse: collapse;
  padding: 6px 12px;`) directly in a `<style>` block in the `<head>` to make the
  table readable — cosmetics only, not a functional requirement.
- Keep the `<div id="chart-container">` as an obvious marker string for STORY-007
  to locate and extend.

## Test Requirements
- Calling `build_html(agg, "")` with a non-empty aggregation result returns a
  string that contains `<!DOCTYPE html>`.
- The returned HTML contains one `<tr>` per agent plus one grand-total row.
- Token counts in the HTML use thousands separators (e.g. `"1,234"`).
- Cost values appear with exactly 6 decimal places (e.g. `"0.001234"`).
- The HTML contains the element `id="chart-container"`.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
