# STORY-004: Inline-Level Markdown Parser

**Index**: 4
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: STORY-002, STORY-003

## Context
Implements Phase 2 of Markdown conversion: inline-level parsing. This is the function that processes raw span text inside paragraphs, headings, and blockquotes and emits the appropriate HTML tags. It replaces the identity-function stub left by STORY-002. It calls `embed_image()` from STORY-003 when handling image syntax.

## Acceptance Criteria
- [ ] An `inline_parse(text: str, base_dir: Path) -> str` function (or equivalent) is implemented.
- [ ] **Auto-escape**: raw `&`, `<`, and `>` characters in non-code spans are replaced with `&amp;`, `&lt;`, `&gt;` before any other substitution, to prevent HTML injection.
- [ ] **Inline code** (`` `code` ``): rendered as `<code>…</code>`. Content inside backticks is HTML-escaped but no further inline processing is applied.
- [ ] **Bold** (`**text**` or `__text__`): rendered as `<strong>…</strong>`.
- [ ] **Italic** (`*text*` or `_text_`): rendered as `<em>…</em>`. Must not conflict with bold (i.e. `**bold**` must not partially match as italic).
- [ ] **Strikethrough** (`~~text~~`): rendered as `<del>…</del>`.
- [ ] **Links** (`[label](url)`): rendered as `<a href="url">label</a>`. The label text itself is recursively inline-parsed.
- [ ] **Images** (`![alt](src)`): calls `embed_image(src, base_dir)` to get the final `src` value, then renders as `<img src="…" alt="alt">`.
- [ ] Processing order prevents double-substitution: inline code spans are extracted first (their content is frozen), then bold, italic, strikethrough, links, and images are processed on the remaining text.
- [ ] The block-level parser (`convert()`) now calls `inline_parse()` on paragraph, heading, and blockquote text. Fenced code block content remains unprocessed.
- [ ] `ParseResult.headings[*].text` stores plain text (no HTML tags) — the slug generator receives raw text, not the inline-parsed HTML.

## Implementation Hints
- Process inline code first by extracting all backtick spans into a placeholder map (e.g. `\x00N\x00`), apply the remaining transforms, then substitute placeholders back. This avoids accidentally bolding or linking text inside code spans.
- Compile all inline regexes at module level. Order of application: code → bold → italic → strikethrough → images → links (images before links because `![` would otherwise be partially consumed by a link pattern).
- Bold/italic disambiguation: match `\*\*` before `\*` and `__` before `_`.
- Do not use recursive regex lookbehind for nesting — keep the implementation flat and substitution-based.

## Test Requirements
- Unit test each inline construct individually.
- Test that `&`, `<`, `>` in paragraph text are escaped.
- Test bold+italic in the same sentence without conflict.
- Test inline code that contains `**bold syntax**` — the bold must NOT be applied inside the code span.
- Test an image tag: verify `embed_image` is called and the resulting `data:` URI appears in the output.
- Test a link whose label contains *italic* text (verifying recursive label parsing).
- Integration test: pass a mixed-content Markdown string through `convert()` and verify the full output contains correctly processed inline markup.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
