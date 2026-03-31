# Kanban Board: Development Guide for Coding Agents

## Overview

This project is a **single-file HTML application**. There is no build step, no bundler, and no external runtime dependencies. The entire application lives in `kanban-board.html` and works by opening it directly in a web browser.

## Running the Application

### Option 1: Direct File Open (Simplest)
```bash
open kanban-board.html
# or on Linux:
xdg-open kanban-board.html
```

### Option 2: Local HTTP Server (Recommended for Development)
```bash
# Using Python 3
python3 -m http.server 8000

# Using Python 2
python -m SimpleHTTPServer 8000

# Using Node.js (if available)
npx http-server
```
Then open `http://localhost:8000/kanban-board.html` in your browser.

**Note:** Using a local server ensures proper cookie handling and avoids browser security restrictions on file:// URLs.

## Testing

This project has no automated test suite. Testing is **manual and browser-based**:

1. Open `kanban-board.html` in a modern browser (Chrome, Firefox, Safari, Edge).
2. Test all interactive features:
   - Create cards by clicking "+ Add Card"
   - Edit cards by clicking the ✏️ icon
   - Delete cards by clicking the 🗑️ icon
   - Drag and drop cards between columns
   - Verify data persists across page refresh (check browser DevTools > Application > Cookies)
   - Test dark mode by toggling OS-level or browser-level dark mode preference
   - Test responsive layout by resizing the browser window below 600px

**Browser DevTools hints:**
- View cookies: Inspect → Application → Cookies → file:// (or localhost:8000)
- Clear cookies: Application → Cookies → Right-click → Delete
- Errors: Console tab

## Development Tools (Optional)

The following tools can be installed for code quality but are **not required** for the application to function:

### Linting & Formatting
```bash
# Install (one-time setup)
npm install --save-dev eslint stylelint htmlhint prettier

# Run linter
npx eslint kanban-board.html  # Check inline <script> block
npx stylelint kanban-board.html  # Check inline <style> block
npx htmlhint kanban-board.html   # Check HTML structure

# Format
npx prettier --write kanban-board.html
```

**Note:** These tools are optional and not required by the application.

## Code Conventions

### Inline Script Block (`<script>`)
- Use strict mode: `'use strict';` at the top
- Use ES6+ syntax (arrow functions, const/let, template literals)
- All code in a single `<script>` block; no modules
- Namespace core functions and state at the module level to avoid globals
- Comments should explain the *why*, not the *what*

### Inline Style Block (`<style>`)
- Use CSS custom properties for theming (e.g., `--color-primary`, `--bg-card`)
- Support dark mode via `@media (prefers-color-scheme: dark)` media query
- Keep selectors simple and avoid deep nesting
- Class names follow BEM convention (e.g., `.column__header`, `.card--overdue`)

### HTML Structure
- Semantic HTML5 (use `<main>`, `<section>`, `<article>`, etc.)
- Use `aria-label` and `aria-hidden` for accessibility
- Form controls must have associated `<label>` elements or `aria-label` attributes
- IDs are only for JavaScript targeting; use classes for styling

## Project Structure

```
workspace/
├── kanban-board.html          # The entire application (single file)
└── CLAUDE.md                  # This file
```

## Data Model

The entire board state is stored in a single JSON object in a browser cookie (`kanban_state`):

```json
{
  "columns": {
    "todo": {
      "cards": [
        {
          "id": "uuid-v4-string",
          "title": "string (required)",
          "description": "string (optional)",
          "priority": "high | medium | low",
          "dueDate": "YYYY-MM-DD | null"
        }
      ]
    },
    "inprogress": { "cards": [] },
    "done": { "cards": [] }
  }
}
```

### State Management
- **Load on startup:** `loadState()` reads the cookie and populates the board. Falls back to empty columns if the cookie doesn't exist.
- **Save on every change:** `saveState(state)` serialises the state to JSON and writes it to the `kanban_state` cookie.
- **Re-render:** `renderBoard(state)` clears and rebuilds all DOM nodes from state.

### UUID Generation
- Use `crypto.randomUUID()` for card IDs (modern browsers).
- Fallback to a simple timestamp-based shim for older browsers if needed.

### Cookie Storage Limits
- Browser cookies are typically limited to 4 KB per domain.
- If the serialised state exceeds **3 800 bytes**, warn the user.
- If card count exceeds **20**, show a dismissible warning banner.

## SortableJS Embedding

The Sortable.js library must be embedded inline in the `<script>` block (no external dependencies). The source is available at https://github.com/SortableJS/Sortable.

Key usage:
```javascript
new Sortable(columnElement, {
  group: 'cards',
  animation: 150,
  onEnd: function(evt) {
    // Handle card movement between columns
    saveState(state);
  }
});
```

## Browser Support

- Modern evergreen browsers (Chrome, Firefox, Safari, Edge)
- ES6+ syntax required (no IE support)
- `crypto.randomUUID()` available (fallback for older browsers if needed)
- Supports `@media (prefers-color-scheme: dark)`

## Agent Exclusion List

Coding Agents must **never read from or write to** these paths:

```
# Dependency management (if npm is used for dev tools)
node_modules/
package-lock.json

# Editor & IDE artifacts
.vscode/
.idea/
*.swp
*.swo
*~

# OS artifacts
.DS_Store
Thumbs.db

# Browser & development caches
.cache/
*.log
```

**Note:** These exclusions only apply if development tools are installed. The core application has no dependencies and no build artifacts.

## Quick Start for Coding Agents

1. Open `kanban-board.html` in a text editor.
2. All code (HTML, CSS, JS) is in a single file; edit inline.
3. Save the file.
4. Refresh the browser to see changes.
5. Test interactively in the browser.
6. No build step, no npm install required to run the application.

---

**Last Updated:** 2026-03-31
**Technology Stack:** HTML5 + CSS3 + Vanilla JavaScript (ES6+) + SortableJS (inlined)
