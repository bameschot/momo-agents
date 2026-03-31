# STORY-003: easy Aggregator

**Index**: 3
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-002

## Context
With raw records available from the data loader, this story implements the aggregation logic that is the analytical core of the tool. It groups records by `(agent, minute bucket)` and computes per-agent totals and a grand-total row — the three data structures that the HTML generator (STORY-005) will consume to populate both the chart and the summary table.

## Acceptance Criteria
- [ ] `aggregate_by_minute(records)` returns a list of dicts, each with keys `minute`, `agent`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`.
- [ ] The `minute` field is the record's `ts` truncated to `YYYY-MM-DDTHH:MM:00Z` (seconds zeroed out, trailing `Z` preserved).
- [ ] Records sharing the same `(agent, minute)` pair have their numeric fields summed.
- [ ] `compute_agent_totals(records)` returns a dict keyed by agent name; each value is a dict with summed `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd` across **all** records for that agent.
- [ ] `compute_grand_total(agent_totals)` returns a single dict with the same five fields summed across all agents.
- [ ] All three functions accept an empty input and return an empty / zero result without raising.
- [ ] `tests/test_aggregator.py` contains at least one test verifying correct minute-bucket grouping and at least one test verifying correct per-agent totalling.

## Implementation Hints
- Truncating to minute: parse `ts` with `datetime.datetime.fromisoformat(ts.rstrip("Z"))`, set `second=0`, `microsecond=0`, then format back to `YYYY-MM-DDTHH:MM:00Z`. On Python 3.8 `fromisoformat` does not support the trailing `Z` — strip it first.
- Use `collections.defaultdict` to accumulate sums per `(agent, minute)` key.
- These should be pure functions (no I/O) so they are straightforward to test.
- Keep all three functions in `token_report.py` (single-file convention from CLAUDE.md).

## Test Requirements
- Given two records for the same agent within the same minute and one record for the same agent in a different minute, `aggregate_by_minute()` should return two bucket dicts with the correct summed values in the shared-minute bucket.
- Given records for two different agents, `compute_agent_totals()` should return a dict with two keys, each holding the correct per-agent sums.
- `compute_grand_total()` applied to a two-agent totals dict should return the combined sum of all fields across both agents.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
