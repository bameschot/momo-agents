# STORY-005: Table of Contents Builder

**Index**: 5
**Attempts**: 1
**Design ref**: design/md-to-html-cli.md
**Depends on**: STORY-002

## Context
Implements `build_toc()`, which takes the ordered list of `Heading` objects (H1–H3 only) produced by `convert()` and generates a nested `<ul>` HTML structure wrapped in a `<nav>` element. The ToC is later embedded as a sticky sidebar by the page renderer (STORY-007). If the heading list is empty, the function returns an empty string so the renderer can suppress the sidebar.

## Acceptance Criteria
- [ ] `build_toc(headings: list[Heading]) -> str` is implemented.
- [ ] Returns an empty string (`""`) when `headings` is empty.
- [ ] Each `Heading` produces an `<li><a href="#<slug>"><text></a></li>` entry.
- [ ] H1 headings → top-level `<li>` items; H2 → nested one level; H3 → nested two levels. The nesting is reflected by opening/closing `<ul>` tags.
- [ ] The function handles level jumps gracefully (e.g. H1 followed immediately by H3 without an H2 in between) — it must not crash and must produce valid, well-nested HTML.
- [ ] The output is wrapped in `<nav aria-label="Table of contents">…</nav>`.
- [ ] Link text (`Heading.text`) is plain text — no HTML tags in the anchor text.
- [ ] The `Heading.slug` values used here are the same slugs that were assigned as `id` attributes on the heading elements in the body HTML (produced by STORY-002), so anchor links correctly jump to the headings.

## Implementation Hints
- Use a stack to track the current nesting level. When the next heading's level is deeper than current, open a new `<ul>`; when shallower, close `<ul>` elements until at the right depth; when the same, just add the `<li>`.
- A clean way is to build a list of strings and join at the end, rather than string concatenation in a loop.
- Be careful with the level-jump case: if current level is 1 and next is 3, open two nested `<ul>` levels, not one.

## Test Requirements
- Test with an empty heading list → returns `""`.
- Test with only H1 headings → flat single-level `<ul>`.
- Test with H1 → H2 → H3 → H2 → H1 sequence → verify correct nesting and de-nesting.
- Test with a level jump (H1 directly followed by H3) → verify well-nested output (no unclosed tags).
- Test that anchor `href` values match the heading slugs exactly.
- Test that `<nav aria-label="Table of contents">` wraps the output.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
