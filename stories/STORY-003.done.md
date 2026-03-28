# STORY-003: medium GameState Initialisation & First-Run Name Prompt

**Index**: 3
**Complexity**: medium
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-002

## Context
On every page load the game must either restore an existing cat from the cookie or walk the user through naming a brand-new one. This story wires together CookieManager, the in-memory `GameState` object, and the `#name-prompt` overlay UI so that a valid, named GameState is always available before any game logic runs.

## Acceptance Criteria
- [ ] A `GameState` object is defined with all required fields: `name`, `hunger`, `happiness`, `health`, `age`, `lastTick`, `neglectSince`, `isDead`, `forceSick`, `cooldowns` (`feed`, `play`, `care`).
- [ ] `GameState.init()` attempts `CookieManager.load()`. If it returns a valid object, the in-memory state is populated from it and the `#name-prompt` overlay is hidden.
- [ ] If `CookieManager.load()` returns `null`, the `#name-prompt` overlay remains visible and the game does not start until the user submits a name.
- [ ] Fresh-state defaults are: `hunger: 80`, `happiness: 80`, `health: 100`, `age: 0`, `lastTick: Date.now()`, `neglectSince: null`, `isDead: false`, `forceSick: false`, `cooldowns: { feed: 0, play: 0, care: 0 }`.
- [ ] The name prompt form validates that the entered name is non-empty (trimmed). It rejects blank submissions and keeps the overlay visible.
- [ ] On valid name submission, `GameState` is populated with fresh defaults plus the entered name; `CookieManager.save()` is called immediately; the overlay is hidden; the game loop begins.
- [ ] `GameState.save()` is a convenience method that calls `CookieManager.save(GameState)` — all components use this to persist any change.

## Implementation Hints
- The `#name-prompt` overlay (from STORY-001) needs an `<input type="text">` and a `<button>` (or form with `submit` event) inside it.
- A loaded cookie may be missing newer fields (schema drift) — use `Object.assign({}, defaults, loaded)` to safely merge and back-fill missing fields.
- `lastTick` from the cookie must be preserved exactly as-is; the DecayEngine (STORY-005) will use it to calculate offline catch-up time.
- Prevent double-initialisation: once the game starts, the submit handler should be removed or guarded.

## Test Requirements
- Clear all cookies, reload the page → `#name-prompt` overlay is visible, game screen is not interactive.
- Submit an empty name → overlay stays visible, no state is created.
- Submit "Mochi" → overlay disappears, `GameState.name === "Mochi"`, cookie `vcat_state` is set.
- Reload the page → overlay does not appear (existing cookie loaded), cat name is "Mochi".
- Manually corrupt the cookie, reload → name prompt appears again (null-load fallback).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
