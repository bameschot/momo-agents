# STORY-002: Block-Level Markdown Parser

**Index**: 2
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: STORY-001

## Context
Implements the first phase of Markdown-to-HTML conversion: block-level parsing. The `convert()` function (or a `MarkdownParser` class it delegates to) walks the raw Markdown text line by line or block by block and emits HTML for each recognized block type. Inline parsing (bold, links, images, etc.) is **not** applied here — block parsing emits raw span text as plain strings, which will be post-processed in STORY-004. This story also collects `Heading` objects for later ToC generation.

## Acceptance Criteria
- [ ] `convert(markdown_text: str, base_dir: Path) -> ParseResult` exists and is callable.
- [ ] **ATX headings** (`#` through `######`): rendered as `<h1>`–`<h6>` with a slug-based `id` attribute. H1–H3 are collected into `ParseResult.headings`; H4–H6 render but are NOT added to `headings`.
- [ ] **Fenced code blocks** (` ``` ` … ` ``` `): rendered as `<pre><code class="language-<lang>">…</code></pre>`. Optional language tag after the opening fence is captured. Content inside is HTML-escaped (no inline processing).
- [ ] **Blockquotes** (`>`): rendered as `<blockquote><p>…</p></blockquote>`. Multi-line blockquotes (consecutive `>` lines) are joined into a single blockquote. Inline processing will be applied in STORY-004.
- [ ] **Unordered lists** (`-`, `*`, `+`): rendered as `<ul><li>…</li></ul>`. Indentation (2 or 4 spaces) creates nested `<ul>` elements.
- [ ] **Ordered lists** (`1.`, `2.`, …): rendered as `<ol><li>…</li></ol>`. Indentation creates nested `<ol>` elements.
- [ ] **Tables** (GFM pipe syntax): rendered as `<table><thead>…</thead><tbody>…</tbody></table>`. Alignment row (`:---`, `:---:`, `---:`) is parsed and reflected via `style="text-align: …"` on `<td>` and `<th>` elements. Malformed tables (e.g. column count mismatch) fall back to a `<pre>` containing the raw block text.
- [ ] **Horizontal rules** (`---`, `***`, `___` on their own line, optionally with spaces): rendered as `<hr>`.
- [ ] **Paragraphs**: all remaining text runs rendered as `<p>…</p>`.
- [ ] `ParseResult.title` is set to the plain text of the first H1 encountered, or `None` if no H1 exists.
- [ ] Slug generation for heading `id` attributes: lowercase, spaces→hyphens, strip non-alphanumeric-hyphen characters; duplicate slugs get `-2`, `-3`, … suffixes.
- [ ] A blank stub for inline processing is called on paragraph/heading/blockquote text (identity function is fine — STORY-004 will replace it).

## Implementation Hints
- Process the Markdown as a list of lines. Use a state machine or a "collect current block then flush" pattern to handle multi-line constructs (fenced code, lists, tables, blockquotes).
- Avoid repeated full-string regex scans for performance — compile all regexes once at module level.
- Fenced code blocks: once inside a fence, accumulate lines verbatim until the closing fence; do NOT apply any inline processing to their contents.
- Lists: track indentation depth via a stack. Each increase in indentation opens a new nested `<ul>`/`<ol>`; each decrease pops it.
- Tables: detect by presence of `|` in the line AND a following separator row. Validate column count; fall back to `<pre>` on mismatch.
- The slug generator should be a standalone helper (e.g. `slugify(text: str) -> str`) so `TocBuilder` (STORY-005) can reuse it.

## Test Requirements
- Unit tests covering each block type in isolation.
- Test nested lists (2 levels deep minimum).
- Test a table with left/center/right alignment columns.
- Test a fenced code block with and without a language tag.
- Test that duplicate heading slugs receive numeric suffixes.
- Test that a malformed table (column count mismatch) produces `<pre>` output.
- Test that H4 headings appear in `body_html` but NOT in `ParseResult.headings`.
- Test that `ParseResult.title` is the first H1 plain text, and `None` when no H1 present.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
