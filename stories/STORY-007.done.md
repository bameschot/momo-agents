# STORY-007: Page Renderer — HTML5 Document Assembly

**Index**: 7
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: STORY-005, STORY-006

## Context
Implements `render_page()`, which combines all produced artifacts — body HTML, ToC HTML, title, inlined CSS, and inlined JavaScript — into a complete, valid HTML5 document string. This is the final assembly step before writing to disk.

## Acceptance Criteria
- [ ] `render_page(result: ParseResult, title: str, toc_html: str) -> str` is implemented.
- [ ] Returns a complete HTML5 document starting with `<!DOCTYPE html>`.
- [ ] `<title>` tag contains the resolved `title` parameter (HTML-escaped).
- [ ] `STYLES` constant is embedded inside a `<style>` tag in `<head>`.
- [ ] A small inline `<script>` block in `<head>` applies the stored `localStorage` theme preference immediately on load (no flash of wrong theme).
- [ ] `SCRIPTS` constant is embedded inside a `<script>` tag just before `</body>`.
- [ ] Document structure uses semantic HTML5 elements: `<header>`, `<main>`, `<article>`, `<aside>` (for the sidebar ToC), `<nav>` (inside `<aside>`), `<footer>` (optional, may be omitted).
- [ ] Theme toggle button (`<button id="theme-toggle">`) is present in `<header>`.
- [ ] **Sidebar ToC**: when `toc_html` is non-empty, it is rendered inside an `<aside>` element to the right of `<article>`. When `toc_html` is empty, the `<aside>` is omitted entirely.
- [ ] **Mobile ToC**: when `toc_html` is non-empty, a `<details><summary>Contents ▼</summary>…</details>` element is rendered above `<article>` (hidden on desktop via CSS from STORY-006).
- [ ] `result.body_html` is embedded inside `<article>`.
- [ ] Generated HTML is valid and well-formed (no unclosed tags, correct nesting).
- [ ] `<html lang="en">` is set.
- [ ] `<meta charset="UTF-8">` and `<meta name="viewport" content="width=device-width, initial-scale=1.0">` are present in `<head>`.

## Implementation Hints
- Use an f-string or string concatenation — no template engine.
- Conditional ToC rendering: `aside_html = f"<aside>…{toc_html}…</aside>" if toc_html else ""`.
- HTML-escape the title for use in the `<title>` tag: replace `&` → `&amp;`, `<` → `&lt;`, `>` → `&gt;`.
- The "no flash" theme `<script>` in `<head>` should be a short inline snippet (4–6 lines), not the full `SCRIPTS` constant.
- Keep the template readable by factoring large sections into local variables (`head`, `body_content`, etc.) before the final f-string join.

## Test Requirements
- Test that `render_page()` returns a string starting with `<!DOCTYPE html>`.
- Test that the `<title>` value appears correctly escaped in the output.
- Test that when `toc_html` is non-empty, both `<aside>` and `<details>` appear in the output.
- Test that when `toc_html` is empty, neither `<aside>` nor `<details>` appears.
- Test that `result.body_html` content appears inside `<article>…</article>`.
- Test that `STYLES` content appears inside a `<style>` tag.
- Test that `SCRIPTS` content appears inside a `<script>` tag.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
