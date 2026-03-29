# Design: Royal Game of Ur

## Overview

A fully self-contained single HTML file implementation of the Royal Game of Ur — one of the oldest known board games, dating to ancient Mesopotamia. Two players compete on the same device (pass-and-play), racing to be the first to bear all seven of their pieces off the board. The implementation follows the Classic / British Museum rules as interpreted by Irving Finkel.

The entire application — markup, styles, and logic — lives in one `.html` file with no external dependencies whatsoever.

---

## Technology Stack

| Layer | Choice |
|---|---|
| Markup | HTML5 (semantic, single file) |
| Styling | CSS3 (custom properties, grid, flexbox, keyframe animations) |
| Logic | Vanilla JavaScript ES6+ (no frameworks, no libraries) |
| Assets | Inline SVG only (board, pieces, dice faces, rosette decorations) |
| Fonts | System font stack (no web fonts; avoids external requests) |

---

## Project Structure

Everything lives in a single file:

```
royal-game-of-ur.html
├── <style>          — All CSS (variables, layout, board, pieces, dice, overlays, animations)
└── <script>         — All JS (game state, rules engine, rendering, event handling)
    └── <body>       — Static HTML shell (board grid, UI panels, overlays)
```

No build step. Delivered as one file; open in any modern browser.

---

## Components

### 1. Board Renderer
- Draws the 20-square board as a CSS Grid (3 rows × 8 columns, with 4 cells intentionally hidden to form the cross shape).
- Each square is a `<div>` with a `data-square-id` attribute.
- Rosette squares carry a `rosette` CSS class (renders a decorative flower motif via inline SVG background).
- Squares in the shared battle lane are visually distinguished with a subtle mid-tone.

### 2. Piece Renderer
- Each player has 7 piece elements, injected into the DOM at initialisation.
- Pieces are absolutely positioned over squares using CSS transitions for smooth movement.
- A "waiting" tray below each player's side of the board holds un-entered pieces.
- A "borne-off" tray on the opposite side counts completed pieces.

### 3. Dice Component
- Four binary tetrahedral dice, each rendered as a small diamond SVG.
- State: 0 (dark tip down) or 1 (light tip up).
- On roll: CSS keyframe `spin-tumble` animation plays for ~600 ms, then snaps to result.
- Total (0–4) displayed prominently beneath the dice.
- Roll button is disabled when it is not the current player's roll phase.

### 4. Game State Machine
Phases per turn:
```
ROLL → (if moves exist) SELECT_PIECE → MOVE → (check win) → next player's ROLL
                        (if no moves) AUTO_PASS → next player's ROLL
```

States tracked:
- `currentPlayer` — 0 or 1
- `phase` — `'roll' | 'select' | 'moved' | 'won'`
- `diceResult` — integer 0–4
- `selectedPiece` — piece ID or null
- `validMoves` — array of { pieceId, targetSquare }

### 5. Rules Engine
Pure functions (no side effects); all rules encapsulated here.

Key functions:
- `rollDice()` → array of 4 binary values + sum
- `getValidMoves(player, diceResult, boardState)` → array of legal moves
- `isRosette(squareId)` → boolean
- `wouldCapture(squareId, player)` → boolean
- `applyMove(move, boardState)` → new board state
- `checkWin(player, boardState)` → boolean

### 6. Move Highlighter
- After a roll, calls `getValidMoves()`.
- Adds `.valid-move` CSS class to all squares a piece could move to, and `.movable` to pieces that have at least one valid move.
- Clicking a highlighted square (or a movable piece) executes the move.
- If `validMoves` is empty: triggers auto-pass flow.

### 7. Status Bar
- Single line of text above the board.
- Examples: `"Light's turn — roll the dice"`, `"Shadow moved to the safe rosette — roll again!"`, `"No legal moves for Shadow — turn passes to Light"`.
- Updates reactively after every state transition.

### 8. Win Screen Overlay
- Full-screen semi-transparent overlay with a centred card.
- Displays the winning player name and a decorative motif.
- "Play Again" button calls `resetGame()` — restores full initial state, hides overlay, starts a new game immediately.

---

## Data Model

### Board Squares

The board has 20 active squares arranged in a cross. Squares are identified by a sequential path index **per player** (1–14), plus two virtual positions:

| Position | Meaning |
|---|---|
| 0 | Off-board (waiting to enter) |
| 1–4 | Player's private home lane (right→left) |
| 5–12 | Shared battle lane (left→right, middle row) |
| 13–14 | Player's private end zone (right→left) |
| 15 | Borne off (finished) |

### Grid Coordinates → Path Index mapping

```
Board grid (row, col) — 0-indexed:

Row 0 (Player 1 home/end):  cols 0–3 (home), cols 6–7 (end zone)
Row 1 (Battle lane):        cols 0–7
Row 2 (Player 2 home/end):  cols 0–3 (home), cols 6–7 (end zone)

Player 1 path:
  (0,3)→(0,2)→(0,1)→(0,0)  [pos 1–4, home]
  (1,0)→(1,1)→...→(1,7)    [pos 5–12, battle]
  (0,7)→(0,6)               [pos 13–14, end zone]

Player 2 path:
  (2,3)→(2,2)→(2,1)→(2,0)  [pos 1–4, home]
  (1,0)→(1,1)→...→(1,7)    [pos 5–12, battle]
  (2,7)→(2,6)               [pos 13–14, end zone]
```

### Rosette Squares

| Grid position | Path position (both players) |
|---|---|
| (0, 3) | Player 1 path pos 1 |
| (2, 3) | Player 2 path pos 1 |
| (0, 0) | Player 1 path pos 4 |
| (2, 0) | Player 2 path pos 4 |
| (1, 3) | Both players path pos 8 — **safe square** (no captures) |

### Player Object

```js
{
  id: 0 | 1,
  label: "Light" | "Shadow",
  pieces: [
    { id: string, position: 0–15 }  // × 7
  ],
  borneOff: number   // count of pieces at position 15
}
```

### Game State Object

```js
{
  board: Map<squareKey, { player: 0|1, pieceId: string }>,
  players: [Player, Player],
  currentPlayer: 0 | 1,
  phase: 'roll' | 'select' | 'won',
  diceValues: [0|1, 0|1, 0|1, 0|1],
  diceResult: 0–4,
  validMoves: [{ pieceId, fromPos, toPos, captures: bool }],
  selectedPieceId: string | null
}
```

---

## API / Interfaces

This is a purely client-side app with no network layer. The "interface" is the player interaction model:

### User Actions

| Action | Trigger | Condition |
|---|---|---|
| Roll dice | Click "Roll" button | `phase === 'roll'` and it is your turn |
| Select piece | Click a `.movable` piece | `phase === 'select'` |
| Move piece | Click a `.valid-move` square | A piece is selected |
| Play again | Click "Play Again" on win screen | `phase === 'won'` |

### Key JS Functions (public interface of the game module)

```js
initGame()              // Bootstrap — build DOM, bind events, call resetGame()
resetGame()             // Reset state to initial; start Player 1's turn
rollDice()              // Randomise 4 binary dice; compute sum; transition phase
selectPiece(pieceId)    // Mark piece as selected; highlight valid destination squares
movePiece(toPosition)   // Apply move; handle capture / rosette / win / pass
autoPass(reason)        // Display reason message; advance to next player's roll phase
```

---

## Visual Design

### Colour Palette (CSS custom properties)

```css
--bg:            #0f0f14   /* near-black background */
--surface:       #1c1c28   /* board surface */
--surface-alt:   #252535   /* battle lane squares */
--accent-light:  #e8d5a3   /* Player "Light" — warm gold-white */
--accent-shadow: #5b3fa6   /* Player "Shadow" — deep violet */
--rosette:       #c8a84b   /* rosette highlight — antique gold */
--highlight:     #4fc3f7   /* valid move indicator — bright cyan */
--text:          #f0ece0   /* primary text */
--text-muted:    #7a7a9a   /* secondary / muted text */
```

### Layout (mobile-first)

```
┌─────────────────────────────┐
│  Status bar (1 line)        │
├─────────────────────────────┤
│  Shadow's waiting tray      │
├─────────────────────────────┤
│                             │
│        Game Board           │
│    (3-row × 8-col grid)     │
│                             │
├─────────────────────────────┤
│  Light's waiting tray       │
├─────────────────────────────┤
│  Dice row  [● ● ● ●]  Sum   │
│  [ R O L L   D I C E ]      │
└─────────────────────────────┘
```

- Max board width: `min(100vw, 480px)` — centred on desktop.
- Square size: fluid, calculated as `(board-width - gaps) / 8`.
- Touch targets: minimum 44 × 44 px.
- Borne-off pieces displayed as a count badge on each tray.

### Animations

| Event | Animation |
|---|---|
| Dice roll | `spin-tumble` keyframe, 600 ms, ease-out |
| Piece move | CSS `transition: transform 250ms ease` |
| Piece capture | `pop-out` scale + fade, 200 ms |
| Win screen | `fade-in` overlay, 400 ms |
| Valid move highlight | Pulsing `box-shadow` glow on highlighted squares |

---

## Rules Summary (implementation reference)

1. **Setup:** Each player starts with 7 pieces off the board at position 0.
2. **Turn:** Current player rolls 4 binary dice. Sum = number of squares to move (0–4).
3. **Roll 0:** No move possible; turn passes immediately.
4. **Entering a piece:** A piece at position 0 may enter at position `diceResult` (if that square is not occupied by a friendly piece).
5. **Moving:** Advance any one on-board piece by exactly `diceResult` squares along the player's path.
6. **Bearing off:** A piece at position `14 - diceResult == 0` (i.e. it lands exactly on position 15) is borne off. Overshooting is not allowed.
7. **Capture:** Landing on a square occupied by the opponent's piece (positions 5–12 only) sends that piece back to position 0. Cannot capture on the safe rosette (pos 8).
8. **Rosette bonus:** Landing on any rosette square (positions 1, 4, 8 for both players) grants the current player an additional roll immediately.
9. **No legal moves:** If `getValidMoves()` returns an empty array, the turn is automatically passed with a status message.
10. **Win condition:** First player to bear off all 7 pieces wins.

---

## Non-Functional Requirements

| Requirement | Detail |
|---|---|
| Self-containment | Zero external requests; no CDN, no fonts, no images, no web sockets |
| Browser support | All modern evergreen browsers (Chrome, Firefox, Safari, Edge) |
| Mobile / touch | Touch events on pieces and squares; no hover dependency for core flow |
| Performance | No game loop; purely event-driven; negligible CPU/memory footprint |
| Accessibility | ARIA labels on interactive elements; status bar announced via `aria-live` |
| File size | Target < 50 KB (single unminified HTML file) |
| Offline | Works entirely offline; no service worker needed (it's one file) |

---

## Open Questions

_None — all requirements were agreed with the user. The Business Analyst may proceed to write stories._
