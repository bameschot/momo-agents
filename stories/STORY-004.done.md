# STORY-004: Footnote Parsing & Per-File Rendering

**Index**: 4
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: STORY-003

## Context
Adds footnote support to `MarkdownParser`. Footnotes follow the `[^label]` inline reference / `[^label]: definition` block definition syntax. Numbering restarts from 1 for each file parsed (i.e. per `parse()` call). Definitions are collected during parsing and rendered as a `<section class="footnotes">` block appended to the file's HTML fragment.

## Acceptance Criteria
- [ ] Inline footnote references `[^label]` are replaced with `<sup><a href="#fn-{label}" id="fnref-{label}">[N]</a></sup>` where `N` is the 1-based ordinal of first appearance within the current file.
- [ ] Footnote definition lines `[^label]: definition text` are removed from the main body and collected.
- [ ] Footnote definitions support inline Markdown (bold, italic, links, etc.) in their definition text.
- [ ] After the main HTML content, if any footnotes were referenced in the file, a `<section class="footnotes"><ol>` block is appended where each `<li id="fn-{label}">` contains the definition text and a back-link `<a href="#fnref-{label}">↩</a>`.
- [ ] Footnote numbering resets to 1 on each call to `parse()` (per-file scope).
- [ ] A footnote label defined but never referenced in the file is silently ignored (not rendered).
- [ ] A footnote label referenced but not defined renders the superscript link as `[?]` (fallback) and emits a warning to stderr.
- [ ] Multi-line footnote definitions (indented continuation lines following the definition line) are concatenated into the definition text.

## Implementation Hints
- Two-pass strategy for footnotes within the block parser: (1) during the first pass, collect all `[^label]: ...` definition lines and remove them from the line stream; (2) after all blocks are processed, scan the assembled HTML (or inline text) for `[^label]` references and replace them in order of first appearance; (3) append the footnotes section.
- Because inline processing happens inside block content, footnote reference replacement should occur as part of the inline processing pass (STORY-003's pipeline), but the rendering of the footnotes section itself is triggered from `parse()` after all blocks are done.
- Store definitions in a `dict[str, str]` (label → raw definition text) and references in an `list[str]` (ordered by first occurrence) as instance state, reset at the start of each `parse()` call.
- Multi-line definition: if the line immediately following `[^label]: text` is indented by 4 spaces or one tab, it is a continuation. Append it (stripped) to the definition.

## Test Requirements
- Test a file with one inline reference and one definition → correct superscript and footnotes section rendered.
- Test that a second `parse()` call on the same `MarkdownParser` instance resets footnote numbering to 1.
- Test multiple footnotes appear in the `<ol>` in order of first reference appearance, not definition order.
- Test a referenced-but-undefined label → `[?]` rendered, warning on stderr.
- Test a defined-but-unreferenced label → not included in footnotes section.
- Test multi-line footnote definition (indented continuation).
- Test inline Markdown in a definition (e.g. `[^1]: See **bold** here`).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
