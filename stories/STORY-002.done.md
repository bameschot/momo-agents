# STORY-002: Markdown Parser — Block Elements

**Index**: 2
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: STORY-001

## Context
Implements the `MarkdownParser` class covering all block-level Markdown constructs. Inline elements (bold, italic, links, images, etc.) are left as a stub — this story's parser emits raw text inside block containers. The goal is a clean block-structure pass whose output can be tested in isolation before inline processing is layered on in STORY-003.

## Acceptance Criteria
- [ ] `MarkdownParser` class exists in `md_to_html.py` with a public method `parse(markdown: str) -> str` that returns an HTML fragment string.
- [ ] `MarkdownParser` exposes a `headings: list[Heading]` attribute populated after each `parse()` call.
- [ ] ATX headings `#` through `######` are converted to `<h1>`–`<h6>` with an `id` attribute set to the slugified heading text (lowercase, spaces→hyphens, non-alphanumeric stripped, consecutive hyphens collapsed).
- [ ] Blank-line-delimited paragraphs are wrapped in `<p>` tags.
- [ ] Fenced code blocks (triple-backtick ` ``` ` or triple-tilde `~~~`) with an optional language label are rendered as `<pre><code class="language-{lang}">...</code></pre>`; content inside is HTML-escaped (no syntax highlighting).
- [ ] Blockquotes (`>` prefix, nestable) are rendered as `<blockquote>` elements; consecutive `>` lines form one blockquote; `>>` nests.
- [ ] Horizontal rules from `---`, `***`, or `___` (on their own line, optionally with spaces between chars) are rendered as `<hr>`.
- [ ] Unordered lists (`-`, `*`, `+` bullets) are rendered as `<ul><li>` trees; nested lists (indented 2+ spaces or a tab) produce `<ul>` inside `<li>`.
- [ ] Ordered lists (`1.` style) are rendered as `<ol><li>` trees with proper nesting.
- [ ] Task list items `- [ ]` render as `<li><input type="checkbox" disabled> text</li>`; `- [x]` renders with `checked`.
- [ ] GFM pipe tables with an alignment row are rendered as `<table><thead><tr><th>` / `<tbody><tr><td>` with `style="text-align:{left|center|right}"` derived from the alignment row.
- [ ] Hard line breaks (two trailing spaces or a backslash `\` at end of line, within a paragraph) are rendered as `<br>`.
- [ ] Raw HTML lines (lines starting with `<` and ending with `>` or lines that are self-contained HTML tags) are passed through unmodified.
- [ ] Inline content inside block elements is passed through as plain text (the inline stub); this will be replaced in STORY-003.

## Implementation Hints
- A clean approach: split the input into lines, then use a state-machine / multipass approach: first identify block boundaries (fences, blank lines, list continuations, blockquote runs), then emit HTML for each block type.
- Fenced code block content must be HTML-escaped (`<`, `>`, `&`, `"` → entities) before insertion.
- For list nesting, track indentation level. Compare leading whitespace of each list item line to detect nesting. Two spaces or one tab = one extra level.
- Table detection: a line matching `|...|` followed immediately by a separator line matching `|[-: |]+|`.
- Slug generation function (used for heading IDs): lowercase the text, replace spaces with `-`, strip any character that is not alphanumeric or `-`, collapse runs of `-` to a single `-`, strip leading/trailing `-`. Extract this as a module-level helper `slugify(text: str) -> str` for reuse in STORY-005.
- Inline HTML passthrough heuristic: if a stripped line starts with `<` and is a known block-level tag opener (`<div`, `<table`, `<p`, `<ul`, `<ol`, `<pre`, `<blockquote`, `<h1`–`<h6`, `<hr`, `<br`, `<section`, `<nav`, `<article`, `<header`, `<footer`) or is a closing tag `</...>`, pass it through as-is.

## Test Requirements
- Unit-test `MarkdownParser.parse()` directly (no file I/O required).
- Test each block element type with a minimal input/expected-output pair.
- Test nested blockquotes (two levels deep).
- Test nested lists (two levels deep), both ordered and unordered.
- Test a task list mixed with regular list items.
- Test a fenced code block whose content contains `<`, `>`, and `&` to verify HTML escaping.
- Test a pipe table with left, center, and right alignment columns.
- Test that `headings` is populated correctly after `parse()`, including `level`, `text`, and `anchor`.
- Tests can be placed in a `if __name__ == "__main__"` guard or a standalone `test_parser.py` file in `md-to-html/`.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
