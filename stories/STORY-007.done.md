# STORY-007: Scroll-Spy JS, Main Wiring & End-to-End Test

**Index**: 7
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: STORY-006

## Context
The final story. Fills in the `<script>` block with the TOC scroll-spy logic (vanilla JS, no frameworks), completes the `main()` function so it orchestrates the full pipeline (parse → embed → build TOC → assemble → write), and adds an end-to-end smoke test that runs the script against sample `.md` files and validates the output HTML.

## Acceptance Criteria
- [ ] `main()` implements the full pipeline:
  1. `parse_args()` → resolve files and output path.
  2. For each file: read UTF-8 content, instantiate `MarkdownParser(source_path=path)`, call `parse()`, populate a `FileEntry`.
  3. Call `build_toc(entries)` → get `toc` HTML string (also updates all anchor fields in-place).
  4. Construct `RenderContext`.
  5. Call `assemble_html(ctx)` → get the complete HTML string.
  6. Write the HTML string to the output path as UTF-8.
  7. Print a success message to stdout: `Written: {output_path}`.
- [ ] If a source `.md` file has no `#` heading, a warning is printed to stderr: `Warning: {filename} has no top-level heading; using filename as title.`
- [ ] The scroll-spy script in the `<script>` block:
  - Uses `IntersectionObserver` to watch all `<section>` elements.
  - When a section enters the viewport, the corresponding `<a>` element in `#toc` whose `href` matches `#{section.id}` has class `toc-active` added; all others have it removed.
  - Falls back gracefully if `IntersectionObserver` is unavailable (no JS errors; TOC just stays static).
- [ ] CSS for `.toc-active` is defined in the `<style>` block (added in this story or back-ported to STORY-006's CSS): e.g. `font-weight: bold; color: var(--link-color)`.
- [ ] The script is minimal: no external libraries, no `eval`, no `document.write`.
- [ ] An end-to-end test script `md-to-html/test_e2e.py` (or added to an existing test file) does the following:
  - Creates a temporary directory with two sample `.md` files (one with a `# Heading`, one without).
  - Runs `python md_to_html.py "*.md" -o output.html` via `subprocess`.
  - Asserts exit code 0.
  - Reads `output.html` and asserts: `<!DOCTYPE html>` present, `<nav id="toc">` present, both section slugs present as `id=` attributes, at least one `data:image` URI present (if a local image was referenced), footnotes section present (if footnotes were used), `toc-active` CSS class definition present.
  - Asserts the file with no `#` heading emitted a warning on stderr.
  - Asserts the full output is valid UTF-8.

## Implementation Hints
- `IntersectionObserver` approach: observe all `document.querySelectorAll('section[id]')`. Use `rootMargin: "-40% 0px -55% 0px"` so the active section is the one occupying the middle of the viewport.
- For the TOC link lookup: `document.querySelector('#toc a[href="#' + entry.target.id + '"]')`.
- The `main()` pipeline does all parsing serially; no concurrency needed.
- For the missing-heading warning, check `entry.title == entry.slug` after parsing (or track a flag in `MarkdownParser`). Actually, better: after `parse()`, if `parser.headings` is empty or the first heading's level > 1, warn. Most reliably: check if the raw markdown contains a line starting with `# ` at column 0; if not, warn.
- The end-to-end test should be runnable standalone: `python test_e2e.py` exits 0 on success, non-zero with a printed failure message on failure. No third-party test framework required.

## Test Requirements
- End-to-end test (as described in Acceptance Criteria) must pass cleanly.
- Manual browser check: open the generated `output.html`, scroll through sections, confirm TOC highlights the active section.
- Test that the script exits non-zero and prints to stderr when the output directory does not exist (regression from STORY-001).
- Test with `--order` to confirm sections appear in the specified order in the output HTML.
- Test with a recursive glob `"**/*.md"` covering files in subdirectories.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
