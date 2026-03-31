# STORY-002: easy State Manager & Board Initialisation

**Index**: 2
**Complexity**: easy
**Design ref**: workspace/design/kanban-board.processed.md | workspace/design/kanban-board.new.md
**Depends on**: STORY-001

## Context
Adds the JavaScript state layer: reading and writing the `kanban_state` cookie, a UUID generator, and `renderBoard()` which rebuilds the DOM from the state object. After this story the board is interactive enough to show persisted card data across page refreshes, even though card creation and drag-and-drop are not yet wired up.

## Acceptance Criteria
- [ ] On page load, `loadState()` reads the `kanban_state` cookie. If the cookie is absent or its JSON is malformed, the function returns a valid default state with three empty columns (`todo`, `inprogress`, `done`).
- [ ] `saveState(state)` serialises the state object to JSON, URL-encodes it, and writes it to `document.cookie` as `kanban_state=<value>; path=/; SameSite=Lax`. No expiry attribute is set (session cookie).
- [ ] `renderBoard(state)` clears the three column card-list elements and re-populates them from `state.columns`. Each rendered card shows at minimum its title; full card visual detail (priority badge, overdue border, etc.) is added in STORY-003.
- [ ] Each column's card count badge updates to reflect the current number of cards after every `renderBoard()` call.
- [ ] `generateId()` returns a UUID string. It uses `crypto.randomUUID()` when available and falls back to a timestamp-based shim (e.g. `Date.now().toString(36) + Math.random().toString(36).slice(2)`) for older browsers.
- [ ] `DOMContentLoaded` handler calls `loadState()` then `renderBoard()`, so the board is populated immediately on page open.
- [ ] If a previously saved cookie is present, refreshing the page restores all cards to their correct columns.
- [ ] The entire implementation is contained within the single `<script>` block in `kanban-board.html`; `'use strict';` appears at the top.

## Implementation Hints
- Keep state in a module-level variable (`let state = loadState();`) rather than re-reading the cookie on every render.
- Cookie parsing: `document.cookie` returns all cookies as `key=value; key2=value2`. Split on `'; '`, find the entry starting with `kanban_state=`, then `decodeURIComponent()` the value before `JSON.parse()`.
- Wrap `JSON.parse` in a `try/catch` so a corrupted cookie never crashes the app.
- `renderBoard` should iterate `['todo', 'inprogress', 'done']` in order and use `document.getElementById` (or a column lookup map) to find the correct `<ul>` element for each column.
- Card elements created by `renderBoard` need a `data-card-id` and `data-column-id` attribute — these are used by CRUD and drag-and-drop handlers in later stories.

## Test Requirements
- Opening `kanban-board.html` with no existing cookie renders three empty columns with badge `0`.
- Manually setting `document.cookie = 'kanban_state=...'` in the browser console (with a valid JSON payload) and refreshing the page shows the saved cards in the correct columns.
- Setting the cookie to invalid JSON (e.g. `'{'`) and refreshing the page shows three empty columns without a JavaScript error in the console.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
