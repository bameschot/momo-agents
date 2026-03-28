# STORY-014: ThemeAssets & PageRenderer — CSS and HTML Template

**Index**: 14
**Attempts**: 1
**Design ref**: design/md-to-pdf-cli.new.md
**Depends on**: STORY-013

## Context
This story produces the complete, self-contained HTML5 document that will be passed to `wkhtmltopdf`. It has two parts: (1) `STYLES` — a module-level string constant containing print-optimised CSS that replicates the visual appearance of `md2html.py` (light theme only, with `@media print` rules for paginated output), and (2) `render_page()` — the function that assembles the final HTML document from the converted body, ToC sidebar, CSS, and metadata.

## Acceptance Criteria
- [ ] `STYLES` module-level constant contains complete CSS including:
  - Same layout, typography, and colour variables as `md2html.py` — **light theme only** (no `[data-theme="dark"]` block, no theme-toggle button styles).
  - ToC sidebar (`#toc`) styled as a fixed-width right-hand column, readable in paginated PDF output.
  - Code block and `<pre>` styles with `page-break-inside: avoid` to minimise mid-block page breaks.
  - `@media print` rules that: hide any interactive UI elements, ensure the sidebar and main content flow correctly when paginated, and suppress browser-added header/footer chrome.
- [ ] `render_page(result: ParseResult, title: str, toc_html: str) -> str` is implemented:
  - Returns a complete HTML5 document (`<!DOCTYPE html>` … `</html>`).
  - `<title>` is set to `title`.
  - `<style>` block inlines `STYLES`.
  - Body contains a two-column layout: main content area (left/centre) and the ToC sidebar (right), consistent with the layout diagram in the design.
  - When `toc_html` is `""` (no headings), the sidebar element is omitted entirely.
  - No theme-toggle `<button>` element is present.
  - No external stylesheet or script references (fully self-contained).
  - Minimal inline JavaScript only if required for `wkhtmltopdf` anchor-link resolution; omit entirely if not needed.
- [ ] `<title>` reflects the `title` parameter exactly.

## Implementation Hints
- Start from the `md2html.py` `STYLES` constant and `render_page()` / template logic, then strip the dark theme block and theme-toggle button, and add `@media print` rules.
- The two-column layout can use CSS Flexbox or a float-based approach — Flexbox is cleaner. Give the ToC sidebar a fixed width (e.g. `220px`) and the main content area `flex: 1`.
- `wkhtmltopdf` uses QtWebKit, which supports most CSS2 and a good subset of CSS3 — avoid CSS Grid if compatibility is a concern; Flexbox is well-supported.
- `page-break-inside: avoid` on `<pre>` and `<table>` blocks reduces awkward page splits in PDFs.
- The `@media print` block should at minimum set `body { margin: 0; }` and hide any buttons.

## Test Requirements
- `render_page()` with a non-empty `toc_html` → output contains `<!DOCTYPE html>`, `<title>My Title</title>`, the `toc_html` substring, and the `result.body_html` substring.
- `render_page()` with `toc_html=""` → output does NOT contain the ToC sidebar wrapper element.
- Output does not contain `[data-theme`, `dark`, or a theme-toggle `<button>` element.
- Output contains `<style>` with non-empty CSS content.
- The returned string is parseable as valid HTML (no unclosed tags at the document level — a simple check like `output.count("<html") == 1` and `output.count("</html>") == 1` is sufficient).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
