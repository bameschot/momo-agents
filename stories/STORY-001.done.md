# STORY-001: Project Scaffold, Dataclasses & CLI

**Index**: 1
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: none

## Context
This is the foundation story. It creates `md2html.py` as a single executable Python file, defines the shared data model (`Heading`, `ParseResult`), and wires up the `argparse`-based CLI (`parse_args()`). All other stories extend this file. Nothing functional is produced yet — the script should be runnable and print help, but conversion is a no-op stub.

## Acceptance Criteria
- [ ] `md2html.py` exists at the project root and is a single self-contained Python file.
- [ ] The file declares `python3.11+` compatibility (no third-party imports).
- [ ] `Heading` dataclass is defined with fields: `level: int`, `text: str`, `slug: str`.
- [ ] `ParseResult` dataclass is defined with fields: `body_html: str`, `headings: list[Heading]`, `title: str | None`.
- [ ] `parse_args()` is implemented and accepts: positional `input` (path to `.md` file), `-o / --output` (optional output path), `-t / --title` (optional title string), `-h / --help`.
- [ ] Default output path logic: `<input-basename>.html` in the same directory as the input file (computed in `parse_args()` or `main()`).
- [ ] `main()` stub exists: reads args, opens the input file, and prints a placeholder message — no HTML written yet.
- [ ] Running `python md2html.py --help` exits 0 and prints usage.
- [ ] Running `python md2html.py nonexistent.md` exits non-zero with a clear error message.

## Implementation Hints
- Use `from __future__ import annotations` and `from dataclasses import dataclass` — both are stdlib.
- `argparse.FileType('r')` is convenient for the input argument, but using `pathlib.Path` for the positional and validating manually gives better error messages and lets you extract `parent` for default output resolution.
- Keep `main()` guarded by `if __name__ == "__main__": main()`.
- All module-level constants (CSS, JS strings added by later stories) should be defined at the top of the file so the structure is ready for later stories to fill in.

## Test Requirements
- Unit-test `parse_args()` with: a valid `.md` path, an explicit `-o` path, an explicit `-t` title, and the `--help` flag.
- Assert that the default output path is `<same_dir>/<stem>.html` when `-o` is omitted.
- Assert `parse_args()` raises `SystemExit` (or equivalent) for missing positional argument.
- No filesystem writes should occur from these tests.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
