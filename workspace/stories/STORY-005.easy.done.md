# STORY-005: easy Implement fetch_chartjs()

**Index**: 5
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-002

## Context
The generated HTML must be fully self-contained (no internet required to view it).
`fetch_chartjs()` ensures the Chart.js UMD bundle is available by serving it from a
local cache when possible and falling back to a one-time CDN download otherwise.
This story can be implemented in parallel with STORY-003 and STORY-004 because it
only depends on the skeleton from STORY-002.

## Acceptance Criteria
- [ ] `fetch_chartjs(cache_dir: Path) -> str` is fully implemented in
  `workspace/token_report.py` (replaces the stub from STORY-002).
- [ ] If `cache_dir / "chart.umd.min.js"` exists and is non-empty, reads and
  returns its contents as a string without making any network requests.
- [ ] If the cached file does not exist (or `cache_dir` does not exist), creates
  `cache_dir` (including parents), downloads the bundle from
  `https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js` using
  `urllib.request.urlopen`, saves it to the cache path, and returns the content
  as a string.
- [ ] The returned string is non-empty.
- [ ] `ruff check workspace/token_report.py` passes after this change.

## Implementation Hints
- Use `cache_dir.mkdir(parents=True, exist_ok=True)` before writing.
- `urllib.request.urlopen(url).read().decode("utf-8")` is sufficient.
- Write the file in text mode (`Path.write_text(content, encoding="utf-8")`) so
  subsequent reads are consistent.
- The cache path relative to the script is
  `Path(__file__).parent / ".chartjs_cache" / "chart.umd.min.js"`;
  `main()` (a later story) will compute this path and pass it in — `fetch_chartjs`
  itself just uses whatever `cache_dir` it receives.

## Test Requirements
- When called with a `cache_dir` that already contains `chart.umd.min.js`, the
  function returns the cached content and does not make a network request (verify
  by monkeypatching `urllib.request.urlopen` to raise if called).
- When called with a non-existent `cache_dir`, the function creates the directory
  and the cache file (test using a tmp directory, not a live network call — stub
  `urllib.request.urlopen` to return a fake JS string).
- The returned value is a non-empty string in both cases.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
