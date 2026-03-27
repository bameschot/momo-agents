# STORY-003: Markdown Parser — Inline Elements & Image Embedder

**Index**: 3
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: STORY-002

## Context
Completes the `MarkdownParser` by replacing the inline-text stub from STORY-002 with a full inline-element processor. Also implements the standalone `embed_image(path: str, source_md_path: Path) -> str` function. After this story, given a `.md` file, the parser produces a complete HTML fragment with all Markdown features rendered correctly.

## Acceptance Criteria
- [ ] Bold (`**text**`, `__text__`) renders as `<strong>text</strong>`.
- [ ] Italic (`*text*`, `_text_`) renders as `<em>text</em>`.
- [ ] Bold-italic (`***text***`) renders as `<strong><em>text</em></strong>`.
- [ ] Inline code (`` `code` ``) renders as `<code>code</code>`; content inside backticks is HTML-escaped and not further processed for Markdown.
- [ ] Strikethrough (`~~text~~`) renders as `<del>text</del>`.
- [ ] Links `[text](url)` render as `<a href="url">text</a>`.
- [ ] Images `![alt](path)` — local path resolution via `embed_image`; renders as `<img src="{data_uri_or_url}" alt="alt">`.
- [ ] Inline HTML tags (e.g. `<br>`, `<span class="x">`) are passed through unmodified (not double-escaped).
- [ ] Hard line break: two trailing spaces before a newline → `<br>`; backslash `\` immediately before a newline → `<br>`.
- [ ] `embed_image(path, source_md_path)` resolves `path` relative to `source_md_path.parent`; reads the file in binary mode; detects MIME type via `mimetypes.guess_type`; returns `data:{mime};base64,{data}` URI.
- [ ] `embed_image` returns the original `path` string unchanged when: the path starts with `http://` or `https://`, or the resolved local file does not exist/cannot be read.
- [ ] When the parser is invoked with a `source_path: Path` argument (added to `__init__` or `parse()`), inline image references use that path for `embed_image` resolution. When no `source_path` is given, images fall back to the original path.
- [ ] Inline rules are applied in the correct precedence order: code spans first (to prevent Markdown processing inside backticks), then images (before links to avoid `![` being consumed as `[`), then links, then bold/italic/strikethrough.
- [ ] `mimetypes.guess_type` fallback: if MIME cannot be determined, default to `application/octet-stream`.

## Implementation Hints
- Process inline content with a single regex-based substitution pass on the text within each block element's content. Apply substitutions in a pipeline: code spans → escape their contents and reinsert after other passes to avoid double-processing (use a placeholder token technique, e.g. replace `` `...` `` with a UUID token, process other inline elements, then restore).
- Precedence with placeholder tokens: (1) extract code spans to placeholders, (2) extract inline HTML to placeholders, (3) process images `![...]` before links `[...]`, (4) bold-italic before bold before italic before strikethrough, (5) restore placeholders.
- For `mimetypes.guess_type`, call `mimetypes.guess_type(filename)[0]`; if `None`, use `"application/octet-stream"`.
- Bold/italic regex is tricky: use non-greedy matching and ensure `__` doesn't fire mid-word (Python's `re` can handle `(?<!\w)__(?!\s)(.+?)(?<!\s)__(?!\w)`).
- `embed_image` signature: `def embed_image(path: str, source_md_path: Path) -> str`.

## Test Requirements
- Unit-test inline rendering for each element type.
- Test that content inside `` `backticks` `` is not processed for bold/italic/etc.
- Test `![alt](./image.png)` with a real small PNG file present → verify `data:image/png;base64,...` in output.
- Test `![alt](./missing.png)` → original path returned unchanged.
- Test `![alt](https://example.com/img.png)` → URL returned unchanged.
- Test bold-inside-italic: `*_text_*` or `***text***`.
- Test that `&`, `<`, `>` in regular paragraph text are HTML-escaped in the final output.
- Tests may be added to the existing test file from STORY-002.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
