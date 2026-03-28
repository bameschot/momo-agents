# STORY-007: medium ActionHandler — Feed, Play & Care

**Index**: 7
**Complexity**: medium
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-003

## Context
The three player actions are the core interactive mechanic. Each action modifies a stat, sets a cooldown, and triggers a transient animation state. This story implements the business logic for all three actions and wires them to the button click events.

## Acceptance Criteria
- [ ] An `ActionHandler` object with three methods — `feed()`, `play()`, `care()` — is defined.
- [ ] **Feed** (`btn-feed` click):
  - Adds 35 to `GameState.hunger`, capped at 100.
  - Sets `GameState.cooldowns.feed = Date.now() + 120_000` (2-minute cooldown).
  - Sets a transient `eating` animation flag active for 2 seconds.
  - Does nothing and returns early if `GameState.isDead` or the feed cooldown has not expired.
- [ ] **Play** (`btn-play` click):
  - Adds 28 to `GameState.happiness`, capped at 100.
  - Sets `GameState.cooldowns.play = Date.now() + 180_000` (3-minute cooldown).
  - Sets a transient `playing` animation flag active for 2 seconds.
  - Does nothing and returns early if `GameState.isDead`, `GameState.forceSick`, or the play cooldown has not expired.
- [ ] **Care** (`btn-care` click):
  - Adds 40 to `GameState.health`, capped at 100.
  - Clears `GameState.forceSick = false`.
  - Sets `GameState.cooldowns.care = Date.now() + 300_000` (5-minute cooldown).
  - Does nothing and returns early if `GameState.isDead`, the care cooldown has not expired, AND neither `forceSick` is true nor `health < 40`.
  - Note: Care is available when `forceSick === true` OR `health < 40`; cooldown still applies.
- [ ] After any successful action, `GameState.save()` is called immediately.
- [ ] Click event listeners are attached to `#btn-feed`, `#btn-play`, and `#btn-care` during initialisation.
- [ ] Transient animation states (`eating`, `playing`) are stored in a module-level variable (e.g., `ActionHandler.transientState`, `ActionHandler.transientUntil`) so the StateClassifier can read them.

## Implementation Hints
- Cooldown expiry check: `Date.now() >= GameState.cooldowns.feed` → action is available.
- The 2-second transient: set `transientUntil = Date.now() + 2000` and `transientState = 'eating'` (or `'playing'`). The StateClassifier checks `Date.now() < transientUntil`.
- The Care button availability rule (from the design): "Only when sick or health < 40" — the cooldown still runs; if both conditions are false the button is disabled regardless of cooldown. Implement this in both the action guard and the UIRenderer (STORY-009).

## Test Requirements
- Call `ActionHandler.feed()` when `hunger = 50` → hunger becomes 85, cooldown is ~2 min in the future, `transientState === 'eating'`.
- Call `ActionHandler.feed()` again immediately (cooldown active) → hunger unchanged, no second transient.
- Call `ActionHandler.feed()` when `hunger = 90` → hunger capped at 100.
- Call `ActionHandler.play()` when `forceSick = true` → happiness unchanged (blocked).
- Call `ActionHandler.care()` when `health = 80` and `forceSick = false` → care is blocked (neither condition met).
- Call `ActionHandler.care()` when `forceSick = true` → health increases, `forceSick` becomes false.
- Call `ActionHandler.care()` when `health = 30` → health increases by 40 (to 70).
- `GameState.isDead = true` → all three actions return early without mutation.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
