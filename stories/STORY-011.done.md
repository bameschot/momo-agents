# STORY-011: medium Game Loop, Death & Resurrection

**Index**: 11
**Complexity**: medium
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-010

## Context
All the subsystems built in the previous stories must be orchestrated into a cohesive game loop. This final story wires everything together: starts the decay tick, calls the UI renderer, handles the death transition, and implements the resurrection flow (including the post-resurrection name prompt).

## Acceptance Criteria
- [ ] `Game.start()` is called after GameState is initialised (either from cookie or from name-prompt submission). It:
  1. Calls `DecayEngine.catchUp()` to apply any offline decay.
  2. Calls `UIRenderer.render()` immediately for a correct initial render.
  3. Starts `AnimationRenderer.start()`.
  4. Starts a `setInterval` at 10 000 ms (10 seconds) that on each tick:
     a. Calls `DecayEngine.tick(10_000)`.
     b. Calls `NeglectChecker.evaluate()`.
     c. Checks death condition: if `GameState.health <= 0` and not already dead, sets `GameState.isDead = true`.
     d. Calls `StateClassifier.tickSleep()`.
     e. Updates `GameState.lastTick = Date.now()`.
     f. Calls `GameState.save()`.
     g. Calls `UIRenderer.render()`.
- [ ] `UIRenderer.render()` is also called on each 250 ms animation tick so cooldown countdowns update smoothly (it is lightweight enough to call at 4 FPS).
- [ ] **Death flow**: when `isDead` becomes true, `UIRenderer.render()` hides action buttons and shows the `#btn-resurrect` button and the `dead` cat animation.
- [ ] **Resurrection flow** (`#btn-resurrect` click):
  - Shows the `#name-prompt` overlay (with a label indicating the cat died, optional message "Your cat has died. Give your new cat a name:").
  - The overlay's submit handler: validates a non-empty name, resets `GameState` to fresh defaults with the new name, calls `CookieManager.save()`, hides the overlay, and continues the existing game loop (no page reload required).
  - The old cat's death state is fully replaced by the new fresh state.
- [ ] `Game.stop()` clears the game-loop interval and calls `AnimationRenderer.stop()` (used for testing / cleanup).

## Implementation Hints
- A single `setInterval` handle should be stored in a module variable so `Game.stop()` can cancel it cleanly.
- Resurrection reuses the same `Game.start()` flow but since the interval is already running, only reset GameState and let the next tick pick up the fresh state. Alternatively, stop and restart the interval — either approach is acceptable.
- `UIRenderer.render()` called at 4 FPS for countdown updates is fine; it only touches the DOM when values have changed (or always — the overhead is negligible for this app).
- Post-resurrection name prompt can reuse the same `#name-prompt` element from STORY-001 / STORY-003. Update its heading text to communicate death context.

## Test Requirements
- On page load with a valid cookie, `Game.start()` runs without errors; stats update after 10 s intervals.
- Manually set `GameState.health = 1`, wait one tick → `isDead` becomes true, resurrect button appears, action buttons hidden.
- Click resurrect → name prompt appears with a "cat died" message.
- Submit new name "Nova" → game resets with `GameState.name === "Nova"`, fresh stats, `isDead === false`, resurrect button hidden, action buttons visible.
- Reload page after resurrection → "Nova" cookie is present with full fresh state.
- `Game.stop()` halts all intervals; no further console output or DOM changes from the game loop.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
