# STORY-001: easy HTML Skeleton & CSS Theme

**Index**: 1
**Complexity**: easy
**Design ref**: workspace/design/kanban-board.processed.md | workspace/design/kanban-board.new.md
**Depends on**: none

## Context
This is the foundational story that creates the single `kanban-board.html` file. It establishes all static markup and visual styling — the three-column board layout, the hidden card modal overlay, the hidden warning banner, and the complete CSS theme system — so that every subsequent story can wire in JavaScript behaviour on top of a finished visual shell.

## Acceptance Criteria
- [ ] A file `workspace/kanban-board.html` exists and opens in a browser without errors.
- [ ] The page renders three side-by-side columns labelled **To Do**, **In Progress**, and **Done**, each with a visible header and a card count badge (showing `0`).
- [ ] Each column contains a **"+ Add Card"** button at its bottom.
- [ ] A modal overlay element (`<dialog>` or a `<div>` with role="dialog") is present in the DOM but hidden by default; it contains labelled fields for Title (text input), Description (textarea), Priority (select with High/Medium/Low options), and Due Date (date input), plus **Save** and **Cancel** buttons.
- [ ] A warning banner element is present in the DOM but hidden by default; it contains placeholder text and a dismiss button.
- [ ] CSS custom properties (e.g. `--color-primary`, `--bg-card`, `--bg-board`) drive all colours and are defined on `:root`.
- [ ] A `@media (prefers-color-scheme: dark)` block overrides the custom properties so the board is legible in dark mode without any JavaScript.
- [ ] At viewport widths below 600 px the three columns stack vertically (CSS-only, no JS).
- [ ] HTML uses semantic elements (`<main>`, `<section>`, `<article>`, etc.) and BEM class names (e.g. `.column__header`, `.card--overdue`).
- [ ] All form controls have associated `<label>` elements or `aria-label` attributes; the modal has `aria-labelledby` pointing to its title.
- [ ] No JavaScript is required for any of the above — the file is purely HTML + CSS at this stage.

## Implementation Hints
- Place a single `<style>` block in `<head>` and a `<script>` block (empty placeholder or `'use strict';` stub) before `</body>`.
- Define columns as flex children of a `.board` container: `display: flex; gap: 1rem;`. On narrow viewports, switch to `flex-direction: column`.
- Priority badge colour-coding can be done with modifier classes (`.badge--high`, `.badge--medium`, `.badge--low`) mapped to custom property values so dark mode overrides apply automatically.
- Card overdue styling uses a `.card--overdue` modifier class: `border-left: 3px solid var(--color-danger)`.
- Dragging state styling (`.card--dragging`) can be declared here: reduced opacity + `box-shadow`.
- Modal hidden state: `display: none` toggled by a class (e.g. `.modal--open`) added by JS in later stories — declare both states in CSS now.
- Use `<input type="date">` for due date; browsers render a native picker.
- SortableJS will be added in a later story; leave the card list `<ul>` elements as plain lists for now.

## Test Requirements
No behavioural tests required — this story produces only static markup and CSS. Visual verification is done by opening `kanban-board.html` in a browser and checking that the layout, dark mode (toggle via OS preference), and sub-600 px stacking all render correctly.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
