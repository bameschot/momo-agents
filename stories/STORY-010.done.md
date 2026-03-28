# STORY-010: WkhtmltopdfChecker — Dependency Validator

**Index**: 10
**Attempts**: 1
**Design ref**: design/md-to-pdf-cli.new.md
**Depends on**: STORY-009

## Context
`md2pdf.py` requires the external `wkhtmltopdf` CLI to render HTML to PDF. Before attempting any file I/O or conversion work, the script must verify that `wkhtmltopdf` is on `PATH` and fail fast with a clear, actionable error message when it is not. This story implements `check_wkhtmltopdf()` and integrates the call into `main()`.

## Acceptance Criteria
- [ ] `check_wkhtmltopdf()` uses `shutil.which("wkhtmltopdf")` to detect the binary.
- [ ] If **found**: returns `None` silently.
- [ ] If **not found**: prints a multi-line human-readable message to `stderr` that includes:
  - What is missing and why it is required.
  - Install instruction for **macOS**: `brew install wkhtmltopdf`
  - Install instruction for **Linux**: `sudo apt-get install wkhtmltopdf` and a note to visit https://wkhtmltopdf.org/downloads.html for other distros.
  - Install instruction for **Windows**: download installer from https://wkhtmltopdf.org/downloads.html
  - A note that a modern release (≥ 0.12.x) is required for clickable internal PDF links.
- [ ] After printing the error, exits immediately with code `1`.
- [ ] `main()` calls `check_wkhtmltopdf()` as the very first action (before reading the input file or parsing the Markdown).
- [ ] No version parsing or version enforcement is performed — presence check only.

## Implementation Hints
- `import shutil` is stdlib; `shutil.which("wkhtmltopdf")` returns `None` if not found.
- Use `sys.stderr.write(...)` or `print(..., file=sys.stderr)` for the error output.
- Use `sys.exit(1)` to terminate.
- The function signature from the design is `def check_wkhtmltopdf() -> None`.
- In unit tests, patch `shutil.which` using `unittest.mock.patch` to avoid a real binary dependency.

## Test Requirements
- **Found**: mock `shutil.which` to return a fake path string → assert function returns `None` and nothing is printed to `stderr`.
- **Not found**: mock `shutil.which` to return `None` → assert `SystemExit` with code `1` is raised, and the captured `stderr` output contains the strings `"wkhtmltopdf"`, `"brew"`, `"apt-get"`, and `"wkhtmltopdf.org"`.
- Verify `main()` calls `check_wkhtmltopdf()` before any file read (use mock ordering or check that `SystemExit` is raised even when the input file does not exist).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
