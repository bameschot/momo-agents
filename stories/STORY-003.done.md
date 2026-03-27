# STORY-003: Chapter Title Extraction (`extract_chapter_title`)

**Index**: 3
**Attempts**: 1
**Design ref**: design/md-to-epub.md
**Depends on**: STORY-001

## Context
Each EPUB chapter needs a human-readable title for the table of contents and spine. This function extracts it cheaply from raw Markdown text before the full parse, falling back gracefully to the filename stem. It is a pure function with no I/O, so it is easy to test in isolation.

## Acceptance Criteria
- [ ] When the Markdown text contains an ATX-style level-1 heading (`# Some Title`), the function returns the heading text stripped of the leading `# ` and any surrounding whitespace
- [ ] When no level-1 heading is present (including files with only level-2+ headings), the function returns `Path(filename).stem`
- [ ] The function only considers the **first** `# ` heading found; subsequent ones are ignored
- [ ] The heading may appear anywhere in the file (not just the first line) — the scan covers the entire text
- [ ] Inline Markdown within the heading (e.g. `# **Bold** Title`) is returned as plain text (markup stripped): `"Bold Title"` — use a simple regex strip of `*`, `_`, `` ` `` characters rather than a full parse
- [ ] The function signature is exactly `extract_chapter_title(md_text: str, filename: str) -> str`

## Implementation Hints
- A single `re.search(r'^#\s+(.+)', md_text, re.MULTILINE)` is sufficient to find the first ATX h1
- Strip common inline Markdown characters with `re.sub(r'[*_`]', '', heading_text).strip()` — this is intentionally simple; edge cases like nested HTML in headings are out of scope
- `Path(filename).stem` (from `pathlib`) handles the fallback; `filename` may be a full path string like `"chapters/02-history.md"` → stem is `"02-history"`

## Test Requirements
- Input with `# Hello World` → returns `"Hello World"`
- Input with `## Subheading` only → returns the filename stem
- Input with no headings → returns the filename stem
- Input with `# **Bold** Title` → returns `"Bold Title"`
- Input where h1 appears on line 5 (not line 1) → still returns the heading text
- Filename `"path/to/02-history.md"` with no h1 → returns `"02-history"`
- Empty string input → returns the filename stem

---
<!-- Coding Agent appends timestamped failure notes below this line -->
