# STORY-002: easy Data Loader

**Index**: 2
**Complexity**: easy
**Design ref**: workspace/design/token-report.new.md
**Depends on**: STORY-001

## Context
The data loader is responsible for discovering all `*.jsonl` files under the tokens directory, deriving agent names from filenames, and parsing each line into a structured record dict. Robustness is a key requirement: invalid JSON lines must not crash the tool; they are skipped with a warning to stderr. The loader also enforces the requirement that at least one `.jsonl` file is present (exit code 1 otherwise).

## Acceptance Criteria
- [ ] `load_records(tokens_dir: Path) -> list[dict]` is implemented in `workspace/token_report.py`, replacing the stub from STORY-001.
- [ ] All `*.jsonl` files in `tokens_dir` are discovered (non-recursive is sufficient; all files are at the top level per the design).
- [ ] Agent name is derived from the filename stem (e.g. `designer.jsonl` → `"designer"`).
- [ ] Each valid JSON line produces a record dict with keys: `ts`, `agent`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `cost_usd`.
- [ ] Blank lines are silently skipped.
- [ ] Lines that fail `json.loads()` are skipped and a warning is printed to stderr identifying the file and line number.
- [ ] If no `*.jsonl` files are found in `tokens_dir`, the function prints an error to stderr and the tool exits with code 1.
- [ ] Function has a docstring.
- [ ] Code passes `ruff check token_report.py` with no errors.

## Implementation Hints
- Use `pathlib.Path.glob("*.jsonl")` to discover files.
- Iterate with `enumerate(f, 1)` to get 1-based line numbers for warnings.
- Use `json.loads(line.strip())` inside a `try/except json.JSONDecodeError`.
- After parsing, inject `"agent": path.stem` into each record dict.
- Numeric fields (`input_tokens`, etc.) should be cast to `int`/`float` if they arrive as the wrong type — the design guarantees the schema but defensive casting is fine.
- If no files are found, call `sys.exit(1)` after printing to stderr; this keeps error handling consistent with the CLI entry point.

## Test Requirements
Create `tests/test_loader.py`.

- **Valid data**: given a temporary directory with two `.jsonl` files (each containing several valid records), assert that `load_records` returns the correct number of records, agent names match filename stems, and all expected fields are present.
- **Invalid lines skipped**: a file containing one valid line and one malformed JSON line; assert only the valid record is returned and a warning was printed to stderr.
- **No files found**: calling `load_records` on an empty temporary directory causes the process to exit with code 1 (test via `subprocess` or `pytest.raises(SystemExit)`).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
