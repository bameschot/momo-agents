# STORY-007: easy End-to-End Integration

**Index**: 7
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-006

## Context
By this point all components exist as independently tested functions. This story wires them together inside `main()` and assembles the final HTML document. It also adds the outer HTML shell (doctype, head, body, basic CSS) that frames the summary table and chart into a presentable single-page report.

## Acceptance Criteria
- [ ] `main()` in `workspace/token_report.py` calls components in order: `load_records` → `aggregate` → `get_chartjs_bundle` → `render_summary_table` → `render_chart_html`.
- [ ] The returned HTML fragments are assembled into a complete, valid HTML5 document (`<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`).
- [ ] The document includes a `<title>` of "Token Usage Report".
- [ ] A minimal inline `<style>` block provides readable formatting: a legible font, responsive table, and reasonable padding/margins. (No external CSS files; no frameworks required.)
- [ ] The summary table appears above the chart controls and canvas.
- [ ] The generated HTML file is written to CWD with the timestamped filename; the path is printed to stdout.
- [ ] Running `python workspace/token_report.py --tokens-dir <dir>` end-to-end against a directory containing sample `.jsonl` files produces a `.html` file that:
  - Contains the agent names from the sample data.
  - Contains token counts formatted with thousands separators.
  - Contains `RAW_BUCKETS` JS data matching the sample records.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Assemble the final document with an f-string:
  ```python
  html = f"""<!DOCTYPE html>
  <html lang="en">
  <head><meta charset="utf-8"><title>Token Usage Report</title>
  <style>{ ... }</style>
  </head>
  <body>
  {table_html}
  {chart_html}
  </body>
  </html>"""
  ```
- Write the file with `pathlib.Path(output_path).write_text(html, encoding="utf-8")`.
- The `get_chartjs_bundle` cache dir should default to `Path(__file__).parent / ".chartjs_cache"` so it is always relative to the script, not the CWD.

## Test Requirements
Create `tests/test_integration.py`.

- **Full run**: create a temporary directory with two sample `.jsonl` files (three records each, two agents, multiple minutes). Run `python workspace/token_report.py --tokens-dir <tmpdir>` via `subprocess`. Assert:
  - Exit code is 0.
  - Stdout contains a filename matching `token-report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.html`.
  - The generated HTML file exists.
  - The HTML contains both agent names.
  - The HTML contains `RAW_BUCKETS`.
  - The HTML contains `<!DOCTYPE html>`.
- **No `.jsonl` files**: run with an empty temporary directory; assert exit code is 1 and stderr contains an error message.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
