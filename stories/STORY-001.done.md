# STORY-001: easy HTML Skeleton & Nokia CSS Theme

**Index**: 1
**Complexity**: easy
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: none

## Context
The entire application lives in a single self-contained `virtual-cat-pet.html` file. This story lays down the structural HTML and all CSS so that subsequent stories have a stable DOM scaffold to attach logic to. No JavaScript is written here — this is purely markup and styling.

## Acceptance Criteria
- [ ] A file `virtual-cat-pet.html` exists at the project root.
- [ ] The page renders in a browser with the Nokia green palette: page background `#0F380F`, screen background `#9BBC0F`, UI chrome `#306230`, button face `#306230`, button text `#9BBC0F`.
- [ ] The layout matches the design wireframe: header with cat name placeholder, a screen area, a stat-bar section, and a button row.
- [ ] The outer widget has a rounded rectangle border and a subtle drop shadow.
- [ ] The screen area has an inner bezel / inset box-shadow simulating an LCD.
- [ ] The `Press Start 2P` Google Font is loaded from CDN with a `monospace` fallback.
- [ ] Buttons have a visible `:active` pressed state (CSS transform or inset shadow).
- [ ] The file contains clearly labelled placeholder `<div>` / `<pre>` elements for: cat animation (`id="cat-screen"`), stat bars (`id="stat-hunger"`, `id="stat-happiness"`, `id="stat-health"`), age/status line (`id="age-label"`, `id="status-label"`), action buttons (`id="btn-feed"`, `id="btn-play"`, `id="btn-care"`), resurrect button (`id="btn-resurrect"`, hidden by default), and name-prompt overlay (`id="name-prompt"`, visible by default).
- [ ] All CSS is inline (inside a `<style>` tag within the file); no external stylesheet.

## Implementation Hints
- Use a centred flex column layout for the widget; `max-width: 360px` keeps it compact.
- The stat bars will later be rendered as `█` Unicode block characters — allocate a `<pre>` or `<span>` with a fixed-width font for each.
- Hide `#btn-resurrect` with `display:none` in CSS; it will be shown by JS later.
- Keep the `#name-prompt` as a full-screen overlay (`position:fixed`, `z-index:100`, same dark-green background) so it covers the game widget on first run.
- The `<pre id="cat-screen">` should use `font-family: monospace`, `white-space: pre`, fixed character dimensions to prevent layout reflow during animation.

## Test Requirements
- Open the file in a browser — no JS errors should appear in the console.
- The Nokia green colour scheme is visible without any JavaScript running.
- All required `id` attributes are present (can be verified with a quick DOM query or simple HTML inspection).
- Resize the viewport — the widget should remain centred and not overflow horizontally on screens ≥ 320 px wide.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
