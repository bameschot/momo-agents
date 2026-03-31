# STORY-004: easy Summary Table HTML Renderer

**Index**: 4
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-003

## Context
This story implements the HTML summary table that appears at the top of the generated report. The table shows per-agent token counts and total cost, with a grand-total row at the bottom. Formatting correctness (thousands separators, cost precision) is a key requirement.

## Acceptance Criteria
- [ ] `render_summary_table(agent_totals: list[dict], grand_total: dict) -> str` is implemented in `workspace/token_report.py`, replacing the stub from STORY-001.
- [ ] Returns an HTML string containing a `<table>` element.
- [ ] Table has a header row with columns: Agent, Input Tokens, Output Tokens, Cache Read Tokens, Cache Write Tokens, Total Cost (USD).
- [ ] One data row per entry in `agent_totals`; rows are in the same order as the input list.
- [ ] A final row labelled **Total** (using `<strong>` or `<th>`) is appended from `grand_total`.
- [ ] Integer token counts are formatted with thousands separators (e.g. `1,234,567`).
- [ ] `cost_usd` is formatted to exactly 6 decimal places (e.g. `0.012345`).
- [ ] Function has a docstring.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Use Python's built-in format spec: `f"{value:,}"` for integers with thousands separators, `f"{value:.6f}"` for cost.
- Build the HTML with string concatenation or an f-string; no templating library needed.
- Wrap integer cells in `<td>` and apply a `text-align: right` style (inline or via a CSS class) so numbers align correctly in the browser.
- The grand-total row can use `<tr class="total-row">` to allow easy styling in the surrounding HTML page.

## Test Requirements
Create `tests/test_summary_table.py`.

- **Correct values**: given two agent-total dicts and a grand-total dict with known values, assert the returned HTML contains the correctly formatted token counts (with commas) and costs (6 dp) for each row.
- **Grand total row**: assert the HTML contains the text "Total" and the correctly summed values.
- **Empty agent list**: `render_summary_table([], grand_total)` returns a valid HTML table containing only the header and the grand-total row without raising.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
