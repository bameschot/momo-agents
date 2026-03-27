# STORY-005: TOC Builder with Anchor Collision Handling

**Index**: 5
**Attempts**: 1
**Design ref**: design/md-to-html.md
**Depends on**: STORY-004

## Context
Implements `build_toc(entries: list[FileEntry]) -> str` which collects all headings across all parsed `FileEntry` objects, guarantees globally unique anchor IDs (deduplicating collisions with a `-2`, `-3` suffix), and renders a nested `<ul>` TOC suitable for the sidebar. Also updates the `anchor` field on each `Heading` object in-place so that the HTML fragment emitted by the parser and the TOC links are in sync.

## Acceptance Criteria
- [ ] `build_toc(entries)` is a module-level function that accepts `list[FileEntry]` and returns an HTML string.
- [ ] The returned HTML is a `<ul>` (no wrapper `<div>`) containing `<li><a href="#{anchor}">{text}</a></li>` entries, with nesting via `<ul>` for deeper heading levels.
- [ ] Nesting is relative: h2 under the nearest preceding h1, h3 under nearest h2, etc. An h3 that appears before any h1/h2 in the document is rendered at the root level.
- [ ] Anchor IDs are globally unique across all entries: if `slugify(heading.text)` produces a value already seen, append `-2`; if that is also taken, `-3`; and so on.
- [ ] The `heading.anchor` field of each `Heading` object is updated in-place to the final (potentially suffixed) unique anchor value before `build_toc` returns, so the parser-emitted `id=` attribute and the TOC `href=` link match.
- [ ] File-level anchors (the `FileEntry.slug` values) are also de-duplicated the same way (slug + `-2`, `-3`) so `<section id=...>` and the TOC entry linking to a section are consistent. The `FileEntry.slug` field is updated in-place.
- [ ] Headings from all files appear in the TOC in document order (file 0 all headings first, then file 1, etc.).
- [ ] All h1–h6 levels are included; no depth cutoff.

## Implementation Hints
- Use a `seen: set[str]` to track all anchors allocated so far (initialise it with file slugs first, since section anchors must also not collide with heading anchors).
- A helper `unique_anchor(base: str, seen: set[str]) -> str` generates a unique slug: tries `base`, then `base-2`, `base-3`, … until unused; adds result to `seen` and returns it.
- Nesting algorithm: maintain a stack of `(level, list_element)` pairs. When the current heading level is deeper than the top of the stack, open a new `<ul>`. When shallower, pop the stack until the level matches or the stack is empty.
- For plain-text heading labels in the TOC, strip any HTML tags from `heading.text` using a simple regex `re.sub(r'<[^>]+>', '', text)` so the TOC shows clean text without markup artifacts.
- `build_toc` should be called after all `FileEntry.html_body` values are populated (i.e., after all files have been parsed), but before `assemble_html`.

## Test Requirements
- Test with two files that both have an `# Introduction` heading → second gets anchor `introduction-2`; TOC `href` and section `id` both reflect the `-2` suffix.
- Test heading nesting: h1 → h2 → h3 → back to h1 produces correct `<ul>` depth.
- Test an h3 appearing before any h1/h2 is placed at root TOC level.
- Test that `FileEntry.slug` collision across two files with the same stem is resolved.
- Test TOC across three files: headings appear in document order.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
