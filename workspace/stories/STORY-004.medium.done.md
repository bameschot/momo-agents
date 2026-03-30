# STORY-004: medium Implement aggregate()

**Index**: 4
**Complexity**: medium
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-003

## Context
`aggregate()` is the computation core of the pipeline. It receives the flat list of
records produced by `load_records()` and returns three things the HTML generator
needs: a list of minute-bucket rows (for the chart), per-agent total rows (for the
summary table), and a grand-total row (for the summary table footer). Getting the
minute-bucket truncation and the summation logic right is the main challenge here.

## Acceptance Criteria
- [ ] `aggregate(records: List[dict]) -> dict` is fully implemented in
  `workspace/token_report.py` (replaces the stub from STORY-002).
- [ ] Returns a dict with exactly three keys: `"buckets"`, `"agent_totals"`,
  `"grand_total"`.
- [ ] **`"buckets"`**: a list of dicts, each with keys `minute`, `agent`,
  `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`,
  `cost_usd`. Each dict represents the sum of all records sharing the same
  `(agent, minute)` pair.
- [ ] Minute bucket is derived by replacing the seconds portion of `ts` with
  `":00Z"`, producing the format `YYYY-MM-DDTHH:MM:00Z`.
- [ ] **`"agent_totals"`**: a dict keyed by agent name; each value is a dict with
  keys `input_tokens`, `output_tokens`, `cache_read_tokens`,
  `cache_write_tokens`, `cost_usd` — summed across **all** records for that agent.
- [ ] **`"grand_total"`**: a single dict with the same five keys, equal to the sum
  of all agent totals.
- [ ] Passing an empty list returns `{"buckets": [], "agent_totals": {}, "grand_total": {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0, "cost_usd": 0.0}}`.
- [ ] `ruff check workspace/token_report.py` passes after this change.

## Implementation Hints
- Use `collections.defaultdict` for accumulating bucket sums and agent totals.
- Minute truncation: `ts[:16] + ":00Z"` is the simplest approach (relies on the
  fixed ISO-8601 format `YYYY-MM-DDTHH:MM:SSZ`).
- Sort `"buckets"` by `(minute, agent)` for deterministic output that makes
  chart x-axis labels chronological.
- The `"agent_totals"` dict may be ordered arbitrarily; alphabetical ordering by
  agent name is a nice-to-have for the summary table but not required here.

## Test Requirements
- Given three records for two agents across two different minutes, `aggregate()`
  returns the correct number of bucket rows with summed values, and agent totals
  that equal the sum of all records for each agent.
- Two records with the same `(agent, minute)` are merged into one bucket with
  summed token counts and cost.
- Records in different minutes for the same agent produce separate bucket rows.
- The grand total equals the sum of all records regardless of agent or time.
- An empty input list returns the zero-value structure described above.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
