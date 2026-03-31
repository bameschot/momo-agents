# STORY-005: easy Chart.js Bundle Fetcher and Cache

**Index**: 5
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-001

## Context
The generated HTML report must be fully self-contained (no internet connection required after generation). This is achieved by embedding the Chart.js UMD bundle verbatim inside a `<script>` tag. To avoid re-downloading on every run, the bundle is cached locally at `workspace/.chartjs_cache/chart.umd.min.js`. This story implements that fetch-and-cache mechanism.

## Acceptance Criteria
- [ ] `get_chartjs_bundle(cache_dir: Path) -> str` is implemented in `workspace/token_report.py`, replacing the stub from STORY-001.
- [ ] If `cache_dir / "chart.umd.min.js"` exists, its contents are read and returned without making any network request.
- [ ] If the cached file does not exist, the function downloads Chart.js from `https://cdn.jsdelivr.net/npm/chart.js/dist/chart.umd.min.js` using `urllib.request.urlopen`, saves the content to `cache_dir / "chart.umd.min.js"` (creating `cache_dir` if needed), and returns the content as a string.
- [ ] The returned value is the full JS source as a UTF-8 decoded string.
- [ ] The default `cache_dir` used by `main()` is `Path("workspace/.chartjs_cache")` (relative to CWD).
- [ ] Function has a docstring.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Use `urllib.request.urlopen(url).read()` then `.decode("utf-8")`.
- Use `cache_dir.mkdir(parents=True, exist_ok=True)` before writing.
- Write the file in binary mode (`"wb"`) after encoding back to UTF-8, or in text mode after decoding.
- Keep the CDN URL as a module-level constant so it is easy to update.
- The cache path `.chartjs_cache/chart.umd.min.js` is listed in `.gitignore` by convention — no need to create that file, just document it in a comment.

## Test Requirements
Create `tests/test_chartjs_cache.py`.

- **Cache hit**: write a fake JS string to a temporary cache file; call `get_chartjs_bundle` with that directory; assert the returned string equals the fake content and no network request was made (monkeypatch `urllib.request.urlopen` to raise if called).
- **Cache miss**: call `get_chartjs_bundle` with an empty temporary directory (monkeypatching `urllib.request.urlopen` to return a fake JS bytes response); assert the returned string equals the fake content and the cache file was created with the correct content.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
