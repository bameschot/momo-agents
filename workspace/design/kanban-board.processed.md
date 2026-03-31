# Design: Kanban Board (Single-File HTML App)

## Overview
A self-contained, single HTML file that renders an interactive Kanban board in the browser.
Users can create, edit, delete, and drag-and-drop cards across three fixed columns.
All board state is persisted in a browser cookie and saved automatically on every change.
No server, no build step, no external runtime dependencies — the file works by simply opening it in a browser.

## Technology Stack
| Layer | Choice | Notes |
|---|---|---|
| Markup | HTML5 | Single `.html` file |
| Styling | CSS3 (inline `<style>`) | CSS custom properties for theming; `prefers-color-scheme` media query for dark mode |
| Behaviour | Vanilla JavaScript (inline `<script>`) | ES6+; no module bundler |
| Drag & Drop | SortableJS (inlined in `<script>`) | Full source embedded so no external requests at runtime |
| Persistence | `document.cookie` | JSON-serialised board state; auto-saved on every mutation |

## Project Structure
```
kanban-board.html          # The entire application — one file
```

No external files, no assets, no network requests.

## Components

### 1. Board
- Renders three fixed column containers side-by-side.
- Initialises SortableJS on each column list so cards are draggable both within a column and across columns.
- Calls `saveState()` after every SortableJS `onEnd` event.

### 2. Column
- Fixed labels: **To Do**, **In Progress**, **Done**.
- Each column has an **"+ Add Card"** button at the bottom that opens the Card Modal in *create* mode.
- Displays a card count badge.

### 3. Card
- Displays: **title** (bold), **description** (truncated to 2 lines), **priority badge** (colour-coded), **due date**.
- Visual states:
  - Overdue (due date < today): red left border.
  - Dragging: reduced opacity + drop-shadow.
- Action icons (visible on hover): ✏️ Edit, 🗑️ Delete.

### 4. Card Modal
- Single modal used for both *create* and *edit* modes.
- Fields:
  - **Title** — text input, required.
  - **Description** — textarea, optional.
  - **Priority** — `<select>` with options: High / Medium / Low.
  - **Due Date** — `<input type="date">`, optional.
- Buttons: **Save** (primary) and **Cancel**.
- Pressing Escape or clicking the backdrop closes without saving.

### 5. Card Limit Warning
- After every save, if total card count across all columns exceeds **20**, a dismissible warning banner is shown at the top of the page: *"You have more than 20 cards — cookie storage may be limited."*
- Banner disappears when card count drops back to ≤ 20.

### 6. State Manager
- `loadState()` — reads the cookie, JSON-parses it, and populates the board on page load. Falls back to a sensible default (three empty columns) if no cookie exists or parsing fails.
- `saveState()` — serialises the current board to JSON, writes it to a cookie named `kanban_state` with `path=/`, no expiry (session-persisted) unless the JSON fits within 4 096 bytes. If the serialised payload exceeds **3 800 bytes** (conservative limit), an additional warning is shown.
- `renderBoard()` — full re-render from state; called after load and after any mutation.

## Data Model

### Root state object
```json
{
  "columns": {
    "todo":       { "cards": [ <Card>, ... ] },
    "inprogress": { "cards": [ <Card>, ... ] },
    "done":       { "cards": [ <Card>, ... ] }
  }
}
```

### Card object
```json
{
  "id":          "uuid-v4-string",
  "title":       "string (required)",
  "description": "string (optional, default \"\")",
  "priority":    "high | medium | low",
  "dueDate":     "YYYY-MM-DD | null"
}
```

Card `id` values are generated with `crypto.randomUUID()` (falls back to a timestamp-based UUID shim for older browsers).

## API / Interfaces

This is a purely client-side application with no HTTP API.

### Cookie
| Name | Value | Attributes |
|---|---|---|
| `kanban_state` | URL-encoded JSON string | `path=/; SameSite=Lax` |

### Internal JS interface (module-style, all in one `<script>` block)
| Function | Description |
|---|---|
| `loadState()` | Parse cookie → return state object |
| `saveState(state)` | Serialise state → write cookie; trigger warnings |
| `renderBoard(state)` | Clear DOM columns, re-render all cards |
| `openModal(mode, columnId, card?)` | Show create/edit modal |
| `closeModal()` | Hide modal, clear form |
| `deleteCard(columnId, cardId)` | Remove card from state, re-render, save |
| `isOverdue(dateStr)` | Return `true` if `dateStr` is before today |

## Non-Functional Requirements

| Requirement | Detail |
|---|---|
| **Zero external requests** | SortableJS source inlined; no CDN calls, no fonts, no images |
| **Offline-capable** | Works with no internet connection |
| **Dark mode** | CSS `@media (prefers-color-scheme: dark)` overrides CSS custom properties; no JS needed |
| **Responsive** | Columns stack vertically on narrow viewports (< 600 px) |
| **Accessibility** | Modal traps focus; cards have `aria-label`; colour is not the sole priority indicator (text label always shown) |
| **Cookie limit guard** | Warns at > 20 cards and at payload > 3 800 bytes |
| **Browser support** | Modern evergreen browsers (Chrome, Firefox, Safari, Edge); no IE support required |
| **Performance** | Full re-render on every change is acceptable given the small dataset (≤ 20 cards) |

## Open Questions
_None — all requirements were confirmed with the user during the design session._
