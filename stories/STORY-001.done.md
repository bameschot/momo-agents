# STORY-001: Scaffold, Data Models & CLI

**Index**: 1
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: none

## Context
This is the foundation story. It creates the single script file `md-to-html/md_to_html.py`, defines all shared dataclasses (`FileEntry`, `Heading`, `RenderContext`), and implements the `parse_args` function with full CLI validation. All subsequent stories extend this file. Nothing renders HTML yet — this story exists purely to establish the structure every other component will build on.

## Acceptance Criteria
- [ ] Directory `md-to-html/` exists and contains only `md_to_html.py`.
- [ ] `md_to_html.py` is a single file with no imports outside Python stdlib.
- [ ] `python md_to_html.py --help` prints usage including the `glob` positional argument, `-o/--output`, and `--order` options, then exits 0.
- [ ] Running with a glob that matches zero `.md` files prints a human-readable error to stderr and exits non-zero.
- [ ] Running with `--order` referencing a file not matched by the glob (or not existing on disk) prints an error to stderr and exits non-zero.
- [ ] Running with `-o` pointing to a non-existent parent directory prints an error to stderr and exits non-zero.
- [ ] `parse_args()` returns a namespace/object containing: resolved `list[Path]` of matched files (in glob order, or `--order` override order), output `Path`, and page title (derived from output filename stem).
- [ ] `**` glob patterns work (recursive=True passed to glob.glob).
- [ ] `FileEntry`, `Heading`, and `RenderContext` dataclasses are defined with the exact fields specified in the design.
- [ ] All file I/O uses UTF-8 encoding.
- [ ] A `main()` entry-point function exists and is called under `if __name__ == "__main__":`; it currently just calls `parse_args()` and prints the resolved file list, so manual smoke-testing is possible.

## Implementation Hints
- Use `argparse.ArgumentParser` with `nargs='+'` for `--order`.
- Expand the glob with `pathlib.Path.cwd()` as the base; use `glob.glob(pattern, recursive=True)` and convert results to resolved `Path` objects, then filter to only `.md` files.
- If `--order` is supplied, validate every listed path is in the glob-expanded set (compare resolved absolute paths). Reject extras with a clear message.
- `RenderContext.title` = `output_path.stem` (no extension, no further slugification needed).
- Default output path: `Path("output.html")` relative to cwd.
- Use `@dataclass` from `dataclasses` (stdlib since 3.7).
- Emit all error messages via `print(..., file=sys.stderr)` then `sys.exit(1)`.

## Test Requirements
- Manual CLI smoke tests are sufficient for this story (no automated test framework is introduced yet).
- Test: glob matching zero files → error.
- Test: `--order` with a non-existent path → error.
- Test: `-o /nonexistent_dir/out.html` → error.
- Test: valid glob → prints resolved file list.
- Test: `--help` exits 0 with usage text.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
