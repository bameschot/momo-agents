# STORY-011: MarkdownParser — Block-Level Parsing

**Index**: 11
**Attempts**: 1
**Design ref**: design/md-to-pdf-cli.new.md
**Depends on**: STORY-010

## Context
This story implements Phase 1 (block-level parsing) of the `convert()` function in `md2pdf.py`. It produces the structural HTML skeleton — headings, code blocks, blockquotes, lists, tables, horizontal rules, and paragraphs — and populates the `ParseResult.headings` list. Inline formatting (bold, italic, links, images) is left as plain text pass-through for now; Phase 2 (STORY-012) will apply inline transforms.

## Acceptance Criteria
- [ ] `convert(markdown_text: str, base_dir: Path) -> ParseResult` is implemented (Phase 1 complete, Phase 2 is a pass-through returning the line text unchanged).
- [ ] **ATX headings** (`#` through `######`) — rendered as `<h1>`–`<h6>` with a slug-based `id` attribute; H1–H3 headings are collected into `ParseResult.headings` with correct `level`, `text` (plain text, no HTML), and `slug`.
- [ ] **Fenced code blocks** (` ``` ` … ` ``` `) — content is HTML-escaped and wrapped in `<pre><code>` (optional language class on `<code>` from the opening fence).
- [ ] **Blockquotes** (`>` prefix) — rendered as `<blockquote><p>…</p></blockquote>`; consecutive `>` lines are merged into one blockquote.
- [ ] **Unordered lists** (`-` / `*` / `+` prefixes) with nesting (2- or 4-space indent) — rendered as nested `<ul><li>` structures.
- [ ] **Ordered lists** (digit + `.`) with nesting — rendered as nested `<ol><li>` structures.
- [ ] **Tables** (GitHub-flavoured pipe syntax) — rendered as `<table>` with `<thead>` and `<tbody>`; alignment markers (`:--`, `--:`, `:-:`) are honoured via `style="text-align:…"`.
- [ ] **Horizontal rules** (`---`, `***`, `___`) — rendered as `<hr>`.
- [ ] **Paragraphs** — any non-blank lines not matched by the above are wrapped in `<p>…</p>`; blank lines separate blocks.
- [ ] `ParseResult.title` is set to the plain text of the first H1, or `None` if no H1 exists.
- [ ] Raw `<`, `>`, `&` inside paragraph/heading text and table cells are HTML-escaped at this stage (except inside fenced code blocks).

## Implementation Hints
- Process the Markdown line-by-line, using a state machine or accumulator pattern (same approach as `md2html.py`).
- Slug generation: lower-case the heading text, replace spaces and non-alphanumeric characters with hyphens, strip leading/trailing hyphens. Duplicate slug deduplication (appending `-2`, `-3`, …) is part of STORY-013 (TocBuilder) for ToC links; add the `id` attribute at this stage using a simple seen-slugs counter.
- Fenced code blocks must suppress all other block-level processing while inside the fence.
- Keep a `_slug_counts: dict[str, int]` to track seen slugs and append numeric suffixes for duplicates.

## Test Requirements
- Unit-test each block type in isolation using `convert(text, Path("."))`:
  - Headings: H1–H6 produce correct tags; H1 text is captured as `ParseResult.title`; H1–H3 appear in `headings`; H4–H6 do not appear in `headings`.
  - Fenced code block: content is HTML-escaped; outer `<` / `>` in content become `&lt;`/`&gt;`.
  - Blockquote: consecutive lines merged; rendered as `<blockquote>`.
  - Unordered list: two levels of nesting produce `<ul><li>…<ul><li>…`.
  - Ordered list: same nesting check with `<ol>`.
  - Table: `<thead>`, `<tbody>`, and alignment styles present.
  - Horizontal rule: `<hr>` produced.
  - Paragraph: plain text wrapped in `<p>`.
  - Duplicate H2 slugs: first gets `id="foo"`, second gets `id="foo-2"`.
- No inline formatting is expected in this story's tests (bold, links, etc. may appear as raw text).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
