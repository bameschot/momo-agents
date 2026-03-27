# STORY-006: Theme Assets — Inlined CSS and JavaScript

**Index**: 6
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: STORY-001

## Context
Defines the `STYLES` and `SCRIPTS` module-level string constants in `md2html.py`. These are embedded verbatim into every generated HTML page, making it fully self-contained. The CSS handles layout, typography, light/dark theming, and mobile responsiveness. The JavaScript handles theme toggling (with `localStorage` persistence) and copy-to-clipboard on code blocks.

## Acceptance Criteria
**CSS (`STYLES` constant):**
- [ ] Two-column layout: `<main>` article area (max ~860 px) on the left; `<nav>` ToC sticky bar on the right.
- [ ] CSS custom properties (`--bg`, `--text`, `--code-bg`, etc.) for light theme defaults; `@media (prefers-color-scheme: dark)` overrides them for dark theme.
- [ ] A `data-theme="dark"` attribute on `<html>` (set by JS) forces dark mode regardless of system preference; `data-theme="light"` forces light mode.
- [ ] Typography: readable body font (system stack), monospace for `<code>` / `<pre>`, sensible heading sizes, line height ~1.6.
- [ ] Code blocks (`<pre><code>`): background differentiated from body, horizontal scroll on overflow, padding, rounded corners.
- [ ] Tables: borders, alternating row shading, header background.
- [ ] Blockquotes: left border accent, slightly muted text color.
- [ ] Theme toggle button: fixed/absolute position in the top-right corner, no intrusive styling.
- [ ] Copy button on code blocks: positioned top-right of the `<pre>` block, small, unobtrusive.
- [ ] **Mobile** (`@media (max-width: 768px)`): single-column layout; ToC sidebar hidden; mobile ToC `<details>`/`<summary>` block shown above `<article>`.
- [ ] Horizontal rule styling.
- [ ] Accessible focus outlines not removed.

**JavaScript (`SCRIPTS` constant):**
- [ ] **Theme toggle**: clicking the toggle button cycles between `data-theme="light"` and `data-theme="dark"` on `<html>`. Current preference is saved to `localStorage` under key `"md2html-theme"`. On page load, stored preference is applied before paint (no flash).
- [ ] **Copy button**: each `<pre>` code block gets a copy button injected by JS (not hardcoded in HTML). Clicking copies the `<code>` text content to the clipboard. Button label changes to `"Copied!"` for 2 seconds then reverts to `"Copy"`.
- [ ] JS is minimal, no frameworks, no `eval`.
- [ ] Toggle button initial icon/label reflects the current active theme (☀ for light, 🌙 for dark).

## Implementation Hints
- Define `STYLES = """ … """` and `SCRIPTS = """ … """` near the top of the file, right after the dataclass definitions. Later stories reference them by name.
- For the "no flash" theme application, place a small `<script>` block in the `<head>` (separate from `SCRIPTS`) that reads `localStorage` and sets `data-theme` immediately. The `SCRIPTS` constant (loaded at end of `<body>`) handles the toggle button wiring.
- Copy button injection via JS: `document.querySelectorAll('pre').forEach(pre => { … })` run on `DOMContentLoaded`.
- Use `navigator.clipboard.writeText()` for clipboard access; wrap in try/catch for older browsers.
- The `<details>`/`<summary>` mobile ToC element is rendered in HTML by the page renderer (STORY-007) — the CSS here just controls its visibility relative to viewport width.

## Test Requirements
- Verify `STYLES` is a non-empty string and contains at minimum: `@media (prefers-color-scheme: dark)`, `@media (max-width: 768px)`, `data-theme`, `pre`, `table`.
- Verify `SCRIPTS` is a non-empty string and contains: `localStorage`, `Copied!`, `navigator.clipboard`, `DOMContentLoaded`.
- Manual/visual smoke test: open a generated HTML file in a browser and verify light↔dark toggle works, copy button works, mobile layout collapses the sidebar.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
