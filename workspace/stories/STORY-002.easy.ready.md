# STORY-002: easy CLI Entry Point and Data Loader

**Index**: 2
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-001

## Context
This story creates `workspace/token_report.py` — the single production file for the entire tool — and implements the two lowest-level concerns: the CLI argument parser and the JSONL data loader. Together they form the foundation on which the aggregator and HTML generator (later stories) will be built. Getting the data-loading contract right here means subsequent stories can trust the shape of the records they receive.

## Acceptance Criteria
- [ ] `python workspace/token_report.py --help` exits 0 and documents the `--tokens-dir` option.
- [ ] `python workspace/token_report.py --tokens-dir <missing-path>` exits with code 1 and prints an error to stderr.
- [ ] When `--tokens-dir` points to a directory containing no `*.jsonl` files, the tool exits with code 1 and prints a descriptive error to stderr.
- [ ] The data loader discovers all `*.jsonl` files in the given directory (non-recursive is acceptable).
- [ ] The agent name for each file is the stem of the filename (e.g. `designer.jsonl` → `"designer"`).
- [ ] Each valid JSON line is parsed into a record dict with keys: `ts`, `agent`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`.
- [ ] Blank lines are silently skipped.
- [ ] Lines that fail JSON parsing emit a warning to stderr and are skipped; the tool continues processing the remaining lines.
- [ ] The `tests/test_data_loader.py` file exists and contains at least one passing test that exercises the happy path and at least one test for the malformed-line warning.

## Implementation Hints
- Use `argparse.ArgumentParser` with one optional argument `--tokens-dir` defaulting to `".sentinels/tokens"`.
- Use `pathlib.Path` throughout for file discovery and path manipulation.
- The output filename (`token-report_YYYY-MM-DD_HH-MM-SS.html`) can be generated here with `datetime.datetime.now().strftime(...)` even if the file is not yet written — the placeholder can be wired up properly in STORY-005.
- Keep `load_records(tokens_dir: Path) -> list[dict]` as a standalone function so tests can call it directly.
- `from __future__ import annotations` at the top of the file enables lowercase `list[dict]` generics on Python 3.8.
- Only stdlib imports: `json`, `argparse`, `pathlib`, `sys` for the exit-1 path.

## Test Requirements
- Given a temporary directory with two JSONL files (each containing two valid records and one malformed line), calling `load_records()` should return exactly four records (two per file), each with the correct agent name derived from the filename.
- Given a temporary directory with a file that contains only blank lines, `load_records()` should return an empty list without raising an exception.
- Calling `load_records()` with a path to a non-existent directory should raise an appropriate error (or return an error signal) that causes the CLI to exit 1.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
