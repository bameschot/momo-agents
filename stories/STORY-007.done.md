# STORY-007: Main Entry Point & Integration (`main`)

**Index**: 7
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-006

## Context
`main()` is the top-level entry point that ties every component together into the final runnable CLI tool. It handles argument parsing, input validation, orchestration, output path derivation, EPUB writing, and user-facing messaging. After this story is complete the tool is fully functional end-to-end.

## Acceptance Criteria
- [ ] Calls `parse_args()` to obtain `args`
- [ ] Validates that every path in `args.files` exists and is a readable file; if any do not, prints a clear error message to `sys.stderr` and exits with `sys.exit(1)` — no partial processing
- [ ] If `args.title` is `None`, derives the title from the stem of the **first** input file (e.g. `01-intro.md` → `"01-intro"`)
- [ ] Converts each input file to a `Chapter` by calling `md_file_to_chapter(Path(f))` in the order the user supplied them
- [ ] Calls `build_epub(chapters, args)` to obtain the `EpubBook`
- [ ] Determines the output path:
  - If `args.output` is provided, use that path as-is (converted to `Path`)
  - Otherwise, derive a filename from `args.title`: lowercase, replace spaces with hyphens, append `.epub`, write to the current working directory — e.g. title `"My Novel"` → `Path.cwd() / "my-novel.epub"`
- [ ] Calls `epub.write_epub(str(output_path), book)` to write the file
- [ ] Prints exactly one line to **stdout** on success: `"EPUB written to <absolute output path>"` (use `output_path.resolve()`)
- [ ] All warnings and progress messages go to `sys.stderr`, not stdout
- [ ] If the output directory does not exist (when `--output` points to a non-existent directory), prints an error to stderr and exits with code 1

## Implementation Hints
- Validate files with `Path(f).is_file()` before processing; collect all invalid paths and report them all at once rather than stopping at the first
- Output filename derivation: `title.lower().replace(' ', '-') + '.epub'`
- `epub.write_epub` expects a string path, not a `Path` object — use `str(output_path)`
- Check `output_path.parent.exists()` when `args.output` is not None; CWD always exists so no check needed for the default case
- Wrap `md_file_to_chapter` calls in a loop; exceptions from unreadable files will have already been caught by the pre-validation step

## Test Requirements
- End-to-end: given one temp `.md` file with content, running `main()` with patched `sys.argv` produces a `.epub` file on disk
- The produced `.epub` is a valid ZIP archive (EPUB files are ZIP containers) — `zipfile.is_zipfile(output_path)` returns `True`
- `--output /tmp/out.epub` writes the file to `/tmp/out.epub`
- Without `--output`, title `"My Novel"` produces `my-novel.epub` in CWD
- A missing input file causes `sys.exit(1)` and an error message on stderr; no `.epub` is written
- Multiple input files are combined into a single `.epub` with multiple chapters in order
- `--title` absent → title derived from first filename stem
- `--publisher` absent → no publisher metadata crash; book still written

---
<!-- Coding Agent appends timestamped failure notes below this line -->
