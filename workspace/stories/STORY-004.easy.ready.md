# STORY-004: easy Chart.js Bundle Fetcher and Cache

**Index**: 4
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-001

## Context
The generated HTML must be fully self-contained and work offline, which requires bundling the Chart.js UMD source inline. Downloading it on every run would be slow and fragile, so the tool maintains a local cache. This story implements the fetch-and-cache helper that later stories will call to obtain the Chart.js source string.

## Acceptance Criteria
- [ ] `fetch_chartjs() -> str` returns the full text of the Chart.js UMD min bundle.
- [ ] On the first call (cache absent), the function downloads from `https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js` using `urllib.request` and writes the result to `workspace/.chartjs_cache/chart.umd.min.js`.
- [ ] On subsequent calls (cache present), the function reads from the local cache without making any network request.
- [ ] The cache directory `workspace/.chartjs_cache/` is created automatically if it does not exist.
- [ ] The returned string is non-empty and starts with a JavaScript comment or the `!function` / `(function` preamble typical of a UMD bundle (a basic sanity check).
- [ ] A `tests/test_html_generator.py` file exists (even if it only contains a placeholder import for now — full chart-generation tests come in STORY-005).

## Implementation Hints
- Cache path: `Path(__file__).parent / ".chartjs_cache" / "chart.umd.min.js"` — this makes the cache relative to `token_report.py`, which lives in `workspace/`.
- Use `urllib.request.urlopen` with a reasonable timeout (e.g. 15 seconds).
- Read/write the cache file in text mode with UTF-8 encoding.
- The function should live in `token_report.py` (single-file convention).
- During unit tests, avoid hitting the real network: the test can pre-create the cache file with a dummy JS string and assert that `fetch_chartjs()` returns it without making a network call (monkeypatch `urllib.request.urlopen` or pre-seed the cache).

## Test Requirements
- When a pre-seeded cache file exists at the expected path, `fetch_chartjs()` should return its contents without making any network call (verify by monkeypatching `urllib.request.urlopen` to raise if called).
- No test is required for the live download path; that is implicitly validated by the cache-miss branch at integration time.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
