# STORY-002: CLI Argument Parsing (`parse_args`)

**Index**: 2
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-001

## Context
`parse_args()` is the user-facing contract for the tool. It must define every argument exactly as specified in the design, with the correct types, defaults, and help text. Getting this right early prevents all downstream stories from having to guess about argument names or defaults.

## Acceptance Criteria
- [ ] `parse_args()` returns an `argparse.Namespace` (no `sys.argv` mutation side-effects visible to callers)
- [ ] Positional argument `files` accepts one or more `.md` paths (`nargs='+'`), stored as a list of `str`
- [ ] `--title` is optional; defaults to `None` (resolved in `main()` from the first filename stem)
- [ ] `--author` is optional; defaults to `"Unknown"`
- [ ] `--language` is optional; defaults to `"en"`
- [ ] `--publisher` is optional; defaults to `None` (omitted from EPUB metadata when not supplied)
- [ ] `--cover` is optional; defaults to `None`
- [ ] `--output` is optional; defaults to `None` (resolved in `main()`)
- [ ] `python md_to_epub.py --help` prints usage that matches the design's CLI spec
- [ ] `python md_to_epub.py` (no arguments) exits with a non-zero code and prints an error about missing required positional argument

## Implementation Hints
- Use `argparse.ArgumentParser` with a descriptive `description` string
- Store positional files under `dest='files'` for consistency
- Do **not** convert paths to `Path` objects inside `parse_args`; keep them as strings so `main()` controls path resolution
- `--title` default is `None` rather than a string so that `main()` can detect "not provided" and derive it from the first filename

## Test Requirements
- `parse_args()` can be called with a patched `sys.argv` (e.g., `sys.argv = ['md_to_epub.py', 'a.md']`) and returns the expected namespace
- All defaults are correct when only `files` is supplied
- `--title "My Book"` sets `args.title == "My Book"`
- `--language fr` sets `args.language == "fr"`
- `--publisher` absent → `args.publisher is None`
- `--cover path/to/cover.jpg` sets `args.cover == "path/to/cover.jpg"`
- `--output dist/out.epub` sets `args.output == "dist/out.epub"`

---
<!-- Coding Agent appends timestamped failure notes below this line -->
