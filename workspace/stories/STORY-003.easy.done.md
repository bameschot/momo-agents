# STORY-003: easy Aggregator

**Index**: 3
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-002

## Context
The aggregator takes the flat list of raw records produced by the data loader and produces two derived data structures needed by the HTML generator: (1) minute-bucket rows for the time-series chart, and (2) per-agent totals (plus a grand-total row) for the summary table. All aggregation is in-memory arithmetic — no I/O.

## Acceptance Criteria
- [ ] `aggregate(records: list[dict]) -> dict` is implemented in `workspace/token_report.py`, replacing the stub from STORY-001.
- [ ] The function returns a dict with two keys: `"buckets"` and `"agent_totals"`.
- [ ] `"buckets"` is a list of dicts, each with keys: `minute`, `agent`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`. The `minute` field is the record's `ts` truncated to `YYYY-MM-DDTHH:MM:00Z`.
- [ ] Within the same `(agent, minute)` pair, all numeric fields are summed correctly.
- [ ] Buckets are sorted ascending by `minute` then by `agent` (deterministic ordering for chart rendering).
- [ ] `"agent_totals"` is a list of dicts, each with keys: `agent`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd` — summed across all time for that agent.
- [ ] A `"grand_total"` key in the returned dict holds a single dict with the same fields summed across all agents (agent field set to `"Total"`).
- [ ] Function has a docstring.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Use `collections.defaultdict` keyed on `(agent, minute)` to accumulate bucket sums.
- Truncate the timestamp by slicing the ISO string: `ts[:16] + ":00Z"` (works for strings in `YYYY-MM-DDTHH:MM` prefix form). Alternatively parse with `datetime.datetime.fromisoformat` and replace seconds/microseconds.
- Build `agent_totals` with a second `defaultdict` keyed on `agent`.
- Grand total can be computed from `agent_totals` in a single pass.
- Return value structure: `{"buckets": [...], "agent_totals": [...], "grand_total": {...}}`.

## Test Requirements
Create `tests/test_aggregator.py`.

- **Minute bucketing**: given four records for the same agent where two share the same minute and two differ, assert the result contains exactly three bucket rows with correct summed values in the shared-minute row.
- **Multi-agent totals**: given records from two agents, assert `agent_totals` contains one entry per agent with correct sums, and `grand_total` sums across both agents.
- **Empty input**: `aggregate([])` returns `{"buckets": [], "agent_totals": [], "grand_total": {...all zeros...}}` without raising.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
