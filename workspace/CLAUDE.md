# Royal Game of Ur — Coding Agent Guide

## Project Overview

A fully self-contained single-file implementation of the Royal Game of Ur. The entire deliverable is **`royal-game-of-ur.html`** — one file, no external dependencies, no build step.

The workspace also contains Playwright tests for automated browser-based verification.

---

## File Layout

```
workspace/
├── royal-game-of-ur.html      ← THE deliverable (all markup + CSS + JS)
├── package.json               ← dev dependencies (Playwright only)
├── playwright.config.js       ← Playwright config (points at the HTML file)
├── tests/
│   ├── board.spec.js          ← Board rendering & square layout tests
│   ├── dice.spec.js           ← Dice roll mechanics & animations
│   ├── rules.spec.js          ← Rules engine (moves, captures, rosettes, win)
│   └── gameplay.spec.js       ← Full turn-flow & integration tests
└── CLAUDE.md                  ← This file
```

---

## Install

```bash
npm install
npx playwright install --with-deps chromium
```

> Only needed once. Installs Playwright and the Chromium browser used by tests.

---

## Run Tests

```bash
# Run all tests (headless)
npm test

# Run a single spec file
npx playwright test tests/rules.spec.js

# Run tests with a visible browser (useful when debugging)
npx playwright test --headed

# Show the HTML test report after a run
npx playwright show-report
```

---

## Lint / Format

There is no bundler or transpiler. Use **ESLint** (included as a dev dep) for the inline `<script>` block and **Prettier** for the overall HTML file.

```bash
# Lint the JS inside the HTML file
npm run lint

# Format the HTML file in-place
npm run format

# Check formatting without writing (CI mode)
npm run format:check
```

> ESLint is configured via `.eslintrc.json` to target ES2022 browser globals.

---

## Open the Game Manually

```bash
# macOS
open royal-game-of-ur.html

# Linux
xdg-open royal-game-of-ur.html
```

Or simply drag `royal-game-of-ur.html` into any modern browser. No server required.

---

## Architecture Rules (read before coding)

1. **Single file** — All CSS lives inside the `<style>` tag; all JS lives inside the `<script>` tag at the bottom of `<body>`. No external files, no imports, no CDN links.
2. **No frameworks** — Vanilla JS ES2022+, no React, Vue, jQuery, etc.
3. **No external assets** — Board, pieces, dice faces, and rosette decorations must be inline SVG.
4. **No web fonts** — Use the system font stack only.
5. **Pure rules engine** — Functions in the Rules Engine section must be pure (no DOM side-effects). Only the renderer functions touch the DOM.
6. **CSS custom properties** — All colours must reference the CSS variables defined in the `:root` block (see design doc for palette).
7. **Accessibility** — The status bar `<div id="status">` must carry `aria-live="polite"`. Interactive elements need ARIA labels.
8. **Mobile-first** — Board max-width is `min(100vw, 480px)`, centred. Touch targets ≥ 44 × 44 px.

---

## Key Constants & IDs (do not rename)

| Thing | Value / ID |
|---|---|
| Status bar element | `id="status"` |
| Board container | `id="board"` |
| Dice container | `id="dice"` |
| Roll button | `id="btn-roll"` |
| Win overlay | `id="overlay-win"` |
| Play-again button | `id="btn-play-again"` |
| Player tray (waiting) | `id="tray-p0"` / `id="tray-p1"` |
| Player borne-off tray | `id="borne-p0"` / `id="borne-p1"` |
| Board square | `data-square-id="<row>-<col>"` |
| Piece element | `data-piece-id="<player>-<index>"` |

---

## Game State Shape

```js
// Global singleton — do not rename
let state = {
  board: new Map(),           // squareKey → { player: 0|1, pieceId: string }
  players: [
    { id: 0, label: 'Light',  pieces: [/* 7 × { id, position } */], borneOff: 0 },
    { id: 1, label: 'Shadow', pieces: [/* 7 × { id, position } */], borneOff: 0 },
  ],
  currentPlayer: 0,
  phase: 'roll',              // 'roll' | 'select' | 'won'
  diceValues: [0, 0, 0, 0],
  diceResult: 0,
  validMoves: [],             // [{ pieceId, fromPos, toPos, captures: bool }]
  selectedPieceId: null,
};
```

---

## Public JS Functions (must be implemented with these exact signatures)

```js
function initGame()              // Bootstrap: build DOM, bind events, call resetGame()
function resetGame()             // Reset state; start Player 0's roll phase
function rollDice()              // Randomise diceValues; compute diceResult; transition phase
function selectPiece(pieceId)    // Mark piece selected; highlight valid destination squares
function movePiece(toPosition)   // Apply move; handle capture / rosette / win / pass
function autoPass(reason)        // Show reason in status bar; advance to next player's roll
```

---

## CSS Class Conventions

| Class | Meaning |
|---|---|
| `.rosette` | Rosette square (renders gold flower motif) |
| `.battle-lane` | Shared middle-row squares (cols 0–7, row 1) |
| `.valid-move` | Square that the selected / movable piece can move to |
| `.movable` | Piece that has at least one legal move this turn |
| `.selected` | Currently selected piece |
| `.p0` | Belongs to Player 0 (Light) |
| `.p1` | Belongs to Player 1 (Shadow) |
| `.die-up` | Die face showing 1 (light tip) |
| `.die-down` | Die face showing 0 (dark tip) |
| `.rolling` | Applied during the `spin-tumble` animation (removed after 600 ms) |

---

## Board Path Reference

```
Player 0 (Light):
  pos 1–4  : row 0, cols 3→2→1→0   (private home lane)
  pos 5–12 : row 1, cols 0→1→…→7  (shared battle lane)
  pos 13–14: row 0, cols 7→6       (private end zone)

Player 1 (Shadow):
  pos 1–4  : row 2, cols 3→2→1→0   (private home lane)
  pos 5–12 : row 1, cols 0→1→…→7  (shared battle lane)
  pos 13–14: row 2, cols 7→6       (private end zone)

Rosette positions (path index, same for both players): 1, 4, 8
Shared rosette at path pos 8 = grid (1, 3) — SAFE, no captures here.
```

---

## Environment Variables

None required. This is a fully offline, client-side application.

---

## Target Quality Bar

- All Playwright tests pass.
- `npm run lint` exits 0.
- `npm run format:check` exits 0.
- Single HTML file < 50 KB (unminified).
- Manually playable in Chrome, Firefox, and Safari (latest).
