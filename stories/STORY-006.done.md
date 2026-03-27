# STORY-006: Section Renderer & HTML Assembler with CSS

**Index**: 6
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: STORY-005

## Context
Implements `render_section(entry: FileEntry, index: int) -> str` and `assemble_html(ctx: RenderContext) -> str`. Together these produce the complete, self-contained HTML document. This story also embeds all CSS (light and dark mode, typography, sidebar, alternating section backgrounds) inline in the `<style>` tag.

## Acceptance Criteria
- [ ] `render_section(entry, index)` returns a string containing an optional `<hr class="section-divider">` (omitted when `index == 0`) followed by `<section id="{entry.slug}">…</section>`.
- [ ] Inside the section: a `<div class="section-header"><h1>{entry.title}</h1></div>` is the first child, followed by `entry.html_body`.
- [ ] `assemble_html(ctx)` returns a complete `<!DOCTYPE html>…</html>` string matching the structure defined in the design's *HTML Output Structure* section.
- [ ] The `<title>` tag content equals `ctx.title`.
- [ ] The `<nav id="toc">` sidebar contains `<div id="toc-inner"><p class="toc-title">Contents</p>{ctx.toc}</div>`.
- [ ] Sections alternate between two CSS classes (`section-even`, `section-odd`) applied to each `<section>` element, enabling the alternating background styling.
- [ ] All CSS is in a single `<style>` block in `<head>`; no external stylesheets or `<link>` tags.
- [ ] Light-mode CSS variables match the design spec exactly:
  - Page background: `#f5f5f5`
  - Section background (even): `#ffffff`
  - Section background (odd): `#fafafa`
  - Text: `#1a1a1a`
  - Code block background: `#f0f0f0`
  - Link colour: `#0066cc`
- [ ] Dark-mode overrides (via `@media (prefers-color-scheme: dark)`) match the design spec:
  - Page background: `#1a1a1a`
  - Section background (even): `#242424`
  - Section background (odd): `#2a2a2a`
  - Text: `#e8e8e8`
  - Code block background: `#2f2f2f`
  - Link colour: `#4da6ff`
- [ ] TOC sidebar is fixed-width `260px`, positioned as a sticky/fixed left sidebar; main content area has `max-width: 860px`.
- [ ] Body font: `system-ui, sans-serif`; code font: `ui-monospace, monospace`.
- [ ] The `<script>` block placeholder exists in the output (content is an empty block or a `/* TODO */` comment — filled in by STORY-007).
- [ ] `assemble_html` does not write any files; it only returns the HTML string.

## Implementation Hints
- Use CSS custom properties (`--var`) for colours inside a `:root {}` block with the `@media (prefers-color-scheme: dark)` override on `:root`; this keeps the dark-mode additions minimal.
- Sticky sidebar layout: use CSS `position: fixed; top: 0; left: 0; height: 100vh; overflow-y: auto; width: 260px` on `#toc`. The `<main>` element should have `margin-left: 280px` (sidebar + gap).
- Alternating section backgrounds: use `.section-even { background: var(--bg-section-even); }` and `.section-odd { background: var(--bg-section-odd); }`. In `render_section`, pass `index % 2` to pick the class.
- `render_section` does not need to be a class method; a module-level function is fine.
- `assemble_html` builds the document by string concatenation or a single f-string; either is fine. Keep the CSS literal as a Python multi-line string constant `_CSS = """..."""`.
- The `<hr class="section-divider">` should be rendered between `</section>` and the next `<section>`, not inside either section.

## Test Requirements
- Call `render_section` with `index=0` → no `<hr class="section-divider">` in output.
- Call `render_section` with `index=1` → `<hr class="section-divider">` present before the `<section>`.
- Call `assemble_html` with a minimal `RenderContext` (one entry, empty toc) → output starts with `<!DOCTYPE html>`, contains `<title>`, `<style>`, `<nav id="toc">`, `<main>`, `<script>`, ends with `</html>`.
- Verify `section-even` class on even-indexed sections and `section-odd` on odd-indexed sections.
- Open the generated HTML in a browser (manual check) to confirm light mode styling looks reasonable.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
