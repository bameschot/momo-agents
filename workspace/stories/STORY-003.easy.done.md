# STORY-003: easy Implement load_records()

**Index**: 3
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-002

## Context
`load_records()` is the data-ingestion layer of the tool. It walks a directory for
`*.jsonl` files, treats each filename stem as an agent name, parses every line as a
JSON object, and returns a flat list of records. Robust error handling (skip blank
lines and unparseable lines with a stderr warning) is part of this story. With this
function in place the rest of the pipeline has real data to operate on.

## Acceptance Criteria
- [ ] `load_records(tokens_dir: Path) -> List[dict]` is fully implemented in
  `workspace/token_report.py` (replaces the stub from STORY-002).
- [ ] The function raises `SystemExit(1)` with a message on stderr when
  `tokens_dir` does not exist.
- [ ] The function raises `SystemExit(1)` with a message on stderr when
  `tokens_dir` contains no `*.jsonl` files.
- [ ] Each discovered `*.jsonl` file's stem is used verbatim as the `"agent"` value
  injected into every record from that file.
- [ ] Every non-blank line that is valid JSON produces one record dict with keys:
  `ts`, `agent`, `input_tokens`, `output_tokens`, `cache_read_tokens`,
  `cache_write_tokens`, `cost_usd`.
- [ ] Blank lines are silently skipped.
- [ ] Lines that fail `json.loads()` produce a warning on `sys.stderr`
  (e.g. `"Warning: skipping unparseable line in <file>: <line>"`) and are skipped;
  processing continues.
- [ ] Records from multiple files are combined into a single flat list.
- [ ] `ruff check workspace/token_report.py` passes after this change.

## Implementation Hints
- Use `pathlib.Path.glob("*.jsonl")` to discover files.
- Inject the `"agent"` key by adding it to the parsed dict after `json.loads()`.
- Wrap per-line parsing in `try/except (json.JSONDecodeError, ValueError)`.
- Exit-1 paths: use `print(..., file=sys.stderr); sys.exit(1)`.
- Keep all imports at the top of the file (they were already added in STORY-002).

## Test Requirements
- Given a temp directory with two JSONL files (`designer.jsonl`, `ba.jsonl`), each
  containing two valid records, `load_records()` returns exactly four dicts with
  the correct `agent` values.
- Given a JSONL file that mixes valid lines with one blank line and one
  unparseable line, `load_records()` returns only the valid records and writes
  exactly one warning to stderr.
- Calling `load_records()` with a non-existent path exits with code 1.
- Calling `load_records()` with an empty directory (no `.jsonl` files) exits with
  code 1.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
