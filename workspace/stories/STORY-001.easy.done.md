# STORY-001: easy CLI Scaffold and Entry Point

**Index**: 1
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: none

## Context
This story creates the `workspace/token_report.py` file and establishes the overall program structure. It handles argument parsing, output filename generation, tokens-directory validation, and the top-level `main()` function that will eventually call the loader, aggregator, and HTML-generator components. Subsequent stories fill in those components; this story wires them through stubs so the entry point is executable from day one.

## Acceptance Criteria
- [ ] `workspace/token_report.py` exists and is runnable with `python token_report.py`.
- [ ] `--tokens-dir <path>` argument is accepted; default is `.sentinels/tokens` relative to CWD.
- [ ] When `--tokens-dir` points to a directory that does not exist, the tool prints an error to stderr and exits with code 1.
- [ ] When `--tokens-dir` points to a valid directory, the tool runs to completion (possibly with an empty report if no data yet), prints the output file path to stdout, and exits with code 0.
- [ ] Output filename follows the pattern `token-report_YYYY-MM-DD_HH-MM-SS.html` (using the script's run time; no colons in the timestamp).
- [ ] The file is written to the current working directory.
- [ ] Module and `main()` function have docstrings.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Use `argparse.ArgumentParser` with a single optional argument `--tokens-dir`.
- Use `datetime.datetime.utcnow().strftime("%Y-%m-%d_%H-%M-%S")` to build the filename.
- Use `pathlib.Path` throughout; validate the tokens dir with `.is_dir()`.
- Stub out `load_records`, `aggregate`, `get_chartjs_bundle`, `render_summary_table`, and `render_chart_html` as functions that return empty/placeholder values — they will be replaced by later stories.
- The `main()` function should: parse args → validate dir → call stubs → assemble HTML string → write file → print path.
- Keep stubs in clearly marked sections so coding agents in later stories know exactly where to implement each one.

## Test Requirements
Create `tests/test_cli.py`.

- **Happy path**: invoke `token_report.py` via `subprocess` with `--tokens-dir` pointing to a temporary directory containing at least one `.jsonl` file; assert exit code is 0 and stdout contains a filename matching `token-report_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.html`.
- **Missing directory**: invoke with `--tokens-dir /nonexistent/path`; assert exit code is 1 and stderr contains a meaningful error message.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
