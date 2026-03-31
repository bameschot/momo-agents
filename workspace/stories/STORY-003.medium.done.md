# STORY-003: medium Card Rendering, Modal & CRUD

**Index**: 3
**Complexity**: medium
**Design ref**: workspace/design/kanban-board.processed.md | workspace/design/kanban-board.new.md
**Depends on**: STORY-002

## Context
Completes the full card lifecycle: richly rendered card elements with all visual states, a single reusable modal for creating and editing cards, and delete functionality. After this story a user can add, edit, and delete cards from any column and see all changes persisted to the cookie.

## Acceptance Criteria
- [ ] Each rendered card displays: **title** (bold), **description** (truncated to 2 lines via CSS `line-clamp`), a **priority badge** colour-coded by level (High = red/danger, Medium = amber/warning, Low = green/success), and **due date** formatted as a human-readable string (or blank if `null`).
- [ ] Cards whose `dueDate` is before today's date receive the `.card--overdue` class, producing a red left border.
- [ ] Edit (✏️) and delete (🗑️) action icons are present on every card and visible on hover (CSS `:hover` on the card reveals them).
- [ ] Clicking **"+ Add Card"** on a column opens the modal in *create* mode, with the form fields empty and the modal title showing "Add Card".
- [ ] Clicking the ✏️ icon on a card opens the modal in *edit* mode, pre-populated with that card's current values, and the modal title showing "Edit Card".
- [ ] Clicking **Save** in the modal:
  - Validates that Title is non-empty; if empty, displays an inline validation message and does not close.
  - In create mode: generates a new UUID, appends the card to the correct column in `state`, calls `renderBoard(state)` and `saveState(state)`.
  - In edit mode: updates the existing card object in `state` in-place, calls `renderBoard(state)` and `saveState(state)`.
- [ ] Clicking **Cancel**, pressing **Escape**, or clicking the modal backdrop closes the modal without modifying state.
- [ ] Clicking 🗑️ on a card removes it from `state.columns[columnId].cards`, calls `renderBoard(state)` and `saveState(state)`.
- [ ] The modal traps keyboard focus while open (Tab/Shift-Tab cycle only within modal focusable elements); focus returns to the triggering element when the modal closes.
- [ ] Cards carry `aria-label` attributes (e.g. "Card: <title>, priority <priority>, due <date>").
- [ ] `isOverdue(dateStr)` returns `true` when `dateStr` is a valid `YYYY-MM-DD` string representing a date strictly before today, and `false` for `null`, empty string, or a future/today date.

## Implementation Hints
- Keep `openModal` small: store `{ mode, columnId, cardId }` in a module-level variable so the Save handler can read it without closures over DOM state.
- CSS 2-line clamp: `.card__description { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }` — declare this class in the `<style>` block (can be added here if not already present from STORY-001).
- For the focus trap: on `keydown`, if the key is Tab, check `document.activeElement`; if it is the last focusable element and Tab (not Shift) is pressed, redirect focus to the first focusable element, and vice-versa.
- `isOverdue`: compare `new Date(dateStr)` against `new Date()` after setting hours to 0 on today to avoid timezone edge-cases.
- Priority badge colours should use the same custom properties defined in the CSS theme; this ensures dark-mode compatibility without extra work.
- Backdrop click: attach a click listener to the overlay element; check `event.target === overlayElement` before closing (clicks on the modal card itself should not close).
- For date display, `new Date(dateStr + 'T00:00:00').toLocaleDateString()` avoids UTC-offset display issues.

## Test Requirements
- Clicking "+ Add Card" on "To Do", filling in a title, and clicking Save: the new card appears in the "To Do" column with the correct title; refreshing the page shows the card still there.
- Editing a card's title via the ✏️ icon and saving: the card updates in place; the old title is gone.
- Clicking 🗑️ on a card removes it from the board immediately; refreshing confirms it is gone from the cookie.
- Attempting to save a card with an empty title: the modal stays open and shows a validation error.
- Setting a card's due date to yesterday: the card displays a red left border. Setting it to tomorrow: no red border.
- Pressing Escape while the modal is open: the modal closes without changing any card data.
- Clicking the modal backdrop: the modal closes without changing any card data.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
