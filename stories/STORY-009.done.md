# STORY-009: Project Scaffold, Data Models & CLI

**Index**: 9
**Attempts**: 1
**Design ref**: design/md-to-pdf-cli.new.md
**Depends on**: none

## Context
This is the foundation story for `md2pdf.py`. It creates the single-file Python script, defines the shared data model (`Heading`, `ParseResult`), and wires up the `argparse`-based CLI (`parse_args()`). No PDF conversion logic is implemented yet — the script should be runnable (print help, validate input path) but the pipeline is a no-op stub. All subsequent stories extend this single file.

## Acceptance Criteria
- [ ] `md2pdf.py` exists at the project root and is a single self-contained Python file (Python 3.11+, stdlib only — no third-party imports).
- [ ] `Heading` dataclass is defined with fields: `level: int`, `text: str`, `slug: str`.
- [ ] `ParseResult` dataclass is defined with fields: `body_html: str`, `headings: list[Heading]`, `title: str | None`.
- [ ] `parse_args()` is implemented and accepts:
  - Positional `input` — path to a `.md` file (validated as an existing file).
  - `-o / --output` — optional output PDF path; defaults to `<input-stem>.pdf` in the same directory as the input file.
  - `-t / --title` — optional string to override the HTML `<title>` and document heading.
  - `-h / --help` — prints usage and exits 0.
- [ ] Default output path is computed as `input.parent / (input.stem + ".pdf")`.
- [ ] `main()` stub exists: calls `parse_args()` and prints a placeholder line — no PDF written yet.
- [ ] Running `python md2pdf.py --help` exits 0 and prints usage including all arguments.
- [ ] Running `python md2pdf.py nonexistent.md` exits non-zero with a clear error message to `stderr`.
- [ ] The file includes module-level placeholder constants for `STYLES: str = ""` (to be filled by STORY-014) so the structure is ready for later stories.
- [ ] The script is guarded by `if __name__ == "__main__": main()`.

## Implementation Hints
- Mirror the structure of `md2html.py` closely; this script intentionally parallels it.
- Use `pathlib.Path` for the positional `input` argument and validate manually (`.exists()`, `.is_file()`, suffix check for `.md`) to produce friendly error messages.
- `from __future__ import annotations` ensures forward-reference compatibility.
- Place all future function stubs (`convert`, `build_toc`, `render_page`, `embed_image`, `export_pdf`, `check_wkhtmltopdf`) as bare `def` stubs with `pass` or `raise NotImplementedError` so the file structure is established.

## Test Requirements
- Unit-test `parse_args()` with: a valid `.md` file path, an explicit `-o` output path, an explicit `-t` title, and `--help`.
- Assert default output path is `<same_dir>/<stem>.pdf` when `-o` is omitted.
- Assert `parse_args()` raises `SystemExit` for missing positional argument.
- Assert `parse_args()` raises `SystemExit` (or prints an error) for a path that does not exist.
- No filesystem writes should occur during these tests (use a `tmp_path` fixture or mock).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
