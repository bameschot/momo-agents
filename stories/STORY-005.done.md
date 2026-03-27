# STORY-005: Markdown-to-Chapter Conversion (`md_file_to_chapter`)

**Index**: 5
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-003

## Context
`md_file_to_chapter` is the orchestration layer that ties together file reading, title extraction, Markdown parsing, and image collection into a single `Chapter` object ready for EPUB assembly. It depends on `extract_chapter_title` (STORY-003) and `collect_images` (STORY-004) being implemented first; STORY-004 may be merged in the same session since both are pure utilities.

## Acceptance Criteria
- [ ] The function signature is exactly `md_file_to_chapter(md_path: Path) -> Chapter`
- [ ] Reads the file at `md_path` as UTF-8 text
- [ ] Calls `extract_chapter_title(md_text, str(md_path))` to obtain the chapter title
- [ ] Converts Markdown to HTML using `markdown.markdown(md_text, extensions=['extra', 'tables'])` (the `tables` extension is already included in `extra`, but explicitly listing it is harmless and matches the design intent)
- [ ] Calls `collect_images(html, md_path.parent)` to gather embedded images
- [ ] Returns a `Chapter(title=..., html_body=html, images=...)` dataclass instance
- [ ] If `md_path` does not exist, allows the `FileNotFoundError` to propagate (caller is responsible for pre-validation)

## Implementation Hints
- `md_path.read_text(encoding='utf-8')` is the idiomatic read
- The `markdown` library's `extra` extension bundle includes `tables`, `fenced_code`, `footnotes`, and others — enabling both is fine and ensures broad Markdown support
- `html_body` is the raw HTML fragment string from `markdown.markdown()`; it does NOT need to be a full HTML document (ebooklib wraps it)
- `md_path.parent` for `collect_images` correctly resolves sibling image files relative to the chapter file

## Test Requirements
- Given a temp `.md` file with `# My Chapter\n\nHello world.`, returns `Chapter(title="My Chapter", html_body=<contains "Hello world">, images={})`
- Given a `.md` file with no h1 heading, `chapter.title` equals the file's stem
- Given a `.md` file with a relative `![alt](img.png)` and `img.png` present alongside it, `chapter.images` contains `{"img.png": <bytes>}`
- Given a `.md` file with a missing image, `chapter.images` is empty and a warning is emitted (no exception raised)
- A table in the Markdown (GFM-style `|col|col|`) is rendered as an HTML `<table>` in `html_body`
- Fenced code blocks (` ```python `) are rendered as `<pre><code>` in `html_body`

---
<!-- Coding Agent appends timestamped failure notes below this line -->
