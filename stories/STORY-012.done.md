# STORY-012: MarkdownParser — Inline-Level Parsing & ImageEmbedder

**Index**: 12
**Attempts**: 1
**Design ref**: design/md-to-pdf-cli.new.md
**Depends on**: STORY-011

## Context
This story completes `convert()` by implementing Phase 2 (inline-level parsing) and the `embed_image()` helper. After block parsing produces raw HTML with unformatted text content, the inline pass applies bold, italic, strikethrough, inline code, links, and image transforms — including Base64-inlining of local images. Inlining is critical because the intermediate HTML is written to the system temp directory and `wkhtmltopdf` cannot resolve relative local paths from there.

## Acceptance Criteria
- [ ] `embed_image(src: str, base_dir: Path) -> str` is implemented:
  - If `src` starts with `http://` or `https://`: return `src` unchanged.
  - If `src` is a relative or absolute local path: resolve against `base_dir`, read bytes, detect MIME type from extension (`.png` → `image/png`, `.jpg`/`.jpeg` → `image/jpeg`, `.gif` → `image/gif`, `.webp` → `image/webp`, `.svg+xml` → `image/svg+xml`), and return a `data:<mime>;base64,<data>` URI.
  - If the local file does not exist: print a warning to `stderr` (e.g. `"Warning: image not found: <src>"`), return the original `src` unchanged, and continue (do not abort).
- [ ] Phase 2 inline transforms are applied (in order, to avoid double-substitution) to all text that is not inside a `<pre>` or `<code>` block:
  - Images: `![alt](src)` → `<img alt="alt" src="<embedded_src>">` (calls `embed_image`).
  - Links: `[label](url)` → `<a href="url">label</a>`.
  - Bold: `**text**` or `__text__` → `<strong>text</strong>`.
  - Italic: `*text*` or `_text_` → `<em>text</em>`.
  - Strikethrough: `~~text~~` → `<del>text</del>`.
  - Inline code: `` `code` `` → `<code>code</code>` (content is HTML-escaped).
- [ ] Raw `<`, `>`, `&` that are not part of already-emitted HTML tags are escaped before inline transforms run (or handled consistently so double-escaping does not occur in code spans).
- [ ] `convert()` returns a `ParseResult` with fully-formed `body_html` (block + inline processed).

## Implementation Hints
- Apply inline transforms after block parsing is complete, not during. Iterate over the accumulated block HTML and apply regexes only to text nodes (i.e., skip content already inside `<pre>…</pre>` or `<code>…</code>` tags).
- Order matters: process images before links (both use `](`), process inline code before bold/italic (to avoid mangling backtick content), escape HTML before other transforms.
- Use `re.sub` with a function callback for image substitution so `embed_image` can be called per-match.
- SVG files have MIME type `image/svg+xml` — note this does not follow the extension literally.
- The `base64` module is stdlib: `base64.b64encode(bytes_data).decode('ascii')`.

## Test Requirements
- Unit-test `embed_image()`:
  - HTTP URL → returned unchanged.
  - HTTPS URL → returned unchanged.
  - Existing local `.png` file → returns string starting with `data:image/png;base64,`.
  - Existing local `.jpg` file → returns `data:image/jpeg;base64,…`.
  - Existing local `.svg` file → returns `data:image/svg+xml;base64,…`.
  - Non-existent local file → returns original src; `stderr` contains `"Warning"`.
- Unit-test inline parsing via `convert()`:
  - `**bold**` → `<strong>bold</strong>`.
  - `*italic*` → `<em>italic</em>`.
  - `~~strike~~` → `<del>strike</del>`.
  - `` `code` `` → `<code>code</code>`.
  - `[label](http://example.com)` → `<a href="http://example.com">label</a>`.
  - `![alt](img.png)` with a real temp `.png` file → `data:image/png;base64,` in output.
  - Bold/italic inside a fenced code block → not transformed (rendered as literal `**`/`*`).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
