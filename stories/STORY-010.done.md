# STORY-010: medium UIRenderer — Stat Bars, Labels & Button States

**Index**: 10
**Complexity**: medium
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-009

## Context
Every game tick the player needs to see up-to-date stat bars, age, status text, and buttons that accurately reflect cooldowns and availability. This story implements the DOM-update layer that reads `GameState` and renders it into all non-animation UI elements.

## Acceptance Criteria
- [ ] `UIRenderer.render()` is a function that updates the following DOM elements on every call:
  - **Cat name** in the header (`id="cat-name"` or equivalent) — set to `GameState.name`.
  - **Stat bars**: Each of `#stat-hunger`, `#stat-happiness`, `#stat-health` is rendered as a `█`-character bar where filled blocks = `Math.round(value / 10)` out of 10 (e.g., 70 → `███████░░░`).
  - **Age label** (`#age-label`) — displays `"Day N"` where N = `Math.floor(GameState.age)`.
  - **Status label** (`#status-label`) — displays the current state string from `StateClassifier.classify()`.
  - **Feed button** (`#btn-feed`): disabled and shows cooldown countdown (`"00:XX"`) if cooldown not expired; otherwise enabled with label `"Feed"`.
  - **Play button** (`#btn-play`): disabled if on cooldown or `GameState.forceSick`; shows countdown if on cooldown; label `"Play"`.
  - **Care button** (`#btn-care`): disabled if on cooldown; also disabled if neither `GameState.forceSick` nor `GameState.health < 40`; shows countdown if on cooldown; label `"Care"`.
- [ ] Cooldown countdown format: seconds remaining, zero-padded to 2 digits, prefixed with `"00:"` (e.g., `"00:47"`).
- [ ] When `GameState.isDead`:
  - Hide `#btn-feed`, `#btn-play`, `#btn-care`.
  - Show `#btn-resurrect`.
- [ ] When NOT dead: show action buttons, hide `#btn-resurrect`.
- [ ] `UIRenderer.render()` is safe to call at any time, including before game start (it should be a no-op or handle missing state gracefully).

## Implementation Hints
- Stat bar string: `'█'.repeat(filled) + '░'.repeat(10 - filled)` where `filled = Math.round(GameState.hunger / 10)`.
- Cooldown remaining in ms: `remaining = GameState.cooldowns.feed - Date.now()`. If `remaining <= 0` the button is available.
- Countdown seconds: `Math.ceil(remaining / 1000)` formatted with `String(secs).padStart(2, '0')`.
- Disabling a button: set `.disabled = true` and add a CSS class like `.on-cooldown` for the greyed-out visual.
- Separate the "structurally unavailable" disable (dead, sick blocks play, etc.) from the cooldown disable — they can co-exist in the same render call.

## Test Requirements
- `GameState.hunger = 70` → `#stat-hunger` textContent is `"███████░░░"`.
- `GameState.hunger = 0` → bar is `"░░░░░░░░░░"`.
- `GameState.hunger = 100` → bar is `"██████████"`.
- `GameState.cooldowns.feed = Date.now() + 90_000` → `#btn-feed` is disabled and shows approximately `"00:90"` (decreasing).
- `GameState.isDead = true` → action buttons hidden, resurrect button visible.
- `GameState.isDead = false` → action buttons visible, resurrect button hidden.
- `GameState.forceSick = true` → `#btn-play` is disabled.
- `GameState.health = 80`, `forceSick = false` → `#btn-care` is disabled (condition not met).
- `GameState.health = 35` → `#btn-care` is enabled (health < 40 condition met).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
