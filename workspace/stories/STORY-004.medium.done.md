# STORY-004: medium Drag-and-Drop with Inline SortableJS

**Index**: 4
**Complexity**: medium
**Design ref**: workspace/design/kanban-board.processed.md | workspace/design/kanban-board.new.md
**Depends on**: STORY-003

## Context
Enables drag-and-drop reordering of cards within a column and across columns by embedding the full SortableJS source inline and wiring its `onEnd` event to the state manager. This is the last major interactive feature; after this story the board is functionally complete.

## Acceptance Criteria
- [ ] The full SortableJS library source is embedded inside the single `<script>` block in `kanban-board.html`; the page makes **no external network requests** at any point (verified via browser DevTools → Network tab).
- [ ] SortableJS is initialised on all three column card-list elements after `renderBoard()` runs for the first time, with `group: 'cards'` and `animation: 150`.
- [ ] A card can be dragged to a different position within the same column; the new order is reflected in `state` and the cookie after the drag completes.
- [ ] A card can be dragged from one column to another; the card appears in the destination column and is removed from the source column in both the DOM and `state`.
- [ ] After any drag operation, `saveState(state)` is called so the new order/placement is persisted; refreshing the page preserves the drag result.
- [ ] While a card is being dragged it appears at reduced opacity and with a drop-shadow (`.card--dragging` or SortableJS's ghost class, styled in CSS).
- [ ] SortableJS is re-initialised (or its instances are destroyed and recreated) each time `renderBoard()` is called, so that newly created cards are also draggable without a page refresh.
- [ ] The `onEnd` handler derives the new state by reading card order directly from the DOM (`data-card-id` and `data-column-id` attributes) rather than relying on SortableJS event indices, to ensure correctness across all move scenarios.

## Implementation Hints
- Download the minified SortableJS source from https://raw.githubusercontent.com/SortableJS/Sortable/master/Sortable.min.js and paste it verbatim at the top of the `<script>` block (before `'use strict';` or wrapped in its own IIFE to avoid strict-mode conflicts).
- Keep track of Sortable instances in an array; call `.destroy()` on each before re-initialising in `renderBoard()` to avoid duplicate listeners.
- `onEnd` handler approach: after a drag, iterate `['todo', 'inprogress', 'done']`, query all `[data-card-id]` children of each column list, look up each card object from state by id, and rebuild `state.columns[col].cards` from that order. Then call `saveState(state)`.
- SortableJS ghost element styling: `ghostClass: 'card--dragging'` — add `.card--dragging { opacity: 0.4; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }` to the CSS (or confirm it is already present from STORY-001).
- `handle` option is optional — leaving it unset allows dragging from anywhere on the card, which is fine for this app.

## Test Requirements
- Dragging a card from **To Do** to **In Progress**: the card appears in **In Progress** and is absent from **To Do**; refreshing the page preserves the placement.
- Dragging the second card in a column to the first position: the order is reversed; refreshing the page preserves the new order.
- Creating a new card (via the modal) and then immediately dragging it: the new card is draggable without a page refresh.
- Opening the browser DevTools → Network tab, reloading the page, and interacting with the board: **no external requests** appear.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
