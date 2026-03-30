# STORY-009: easy Implement main() and End-to-End Integration

**Index**: 9
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-008

## Context
With all component functions fully implemented, this story wires them together
inside `main()` and verifies the complete tool works end-to-end: it reads real
JSONL fixtures, aggregates the data, fetches Chart.js (from cache), generates HTML,
writes it to disk, and prints the output path to stdout.

## Acceptance Criteria
- [ ] `main()` is fully implemented in `workspace/token_report.py` (replaces the
  stub from STORY-002).
- [ ] `main()` calls `parse_args()`, then `load_records()`, then `aggregate()`,
  then `fetch_chartjs()`, then `build_html()`, then writes the result to disk.
- [ ] The Chart.js cache directory is computed as
  `Path(__file__).parent / ".chartjs_cache"` and passed to `fetch_chartjs()`.
- [ ] The output filename is `token-report_YYYY-MM-DD_HH-MM-SS.html` where the
  datetime is the wall-clock time at the start of `main()`, formatted with
  `datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")`.
- [ ] The output file is written to the current working directory (not the script
  directory).
- [ ] On success, `main()` prints the absolute path of the generated file to
  stdout (e.g. `print(str(output_path.resolve()))`).
- [ ] `ruff check workspace/token_report.py` passes.
- [ ] Running `python workspace/token_report.py --tokens-dir .sentinels/tokens`
  from the project root (where `.sentinels/tokens/` contains at least one `.jsonl`
  file) exits with code 0 and writes a valid HTML file to CWD.

## Implementation Hints
- Use `datetime.utcnow()` (available in Python 3.8) for timestamp; avoid
  `datetime.now(timezone.utc)` if 3.8 compatibility is a concern (both work, but
  the guide uses `utcnow`).
- `Path.write_text(html, encoding="utf-8")` is the simplest write call.
- The `if __name__ == "__main__": main()` guard is already in place from
  STORY-002 — no changes needed there.

## Test Requirements
- Running `python workspace/token_report.py --tokens-dir <fixture_dir>` (where
  `<fixture_dir>` contains at least one valid `.jsonl` file) exits with code 0,
  prints a path ending in `.html` to stdout, and the file exists on disk with
  non-zero size.
- The output filename matches the pattern `token-report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.html`.
- Running with a non-existent `--tokens-dir` exits with code 1 and prints a
  message to stderr.
- The generated HTML file contains `<!DOCTYPE html>` confirming it is a valid
  HTML document.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
