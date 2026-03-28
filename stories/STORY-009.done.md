# STORY-009: easy AnimationRenderer

**Index**: 9
**Complexity**: easy
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-008

## Context
The cat must visually animate at ~4 FPS by alternating between the two frames of the current state. This story wires `CAT_FRAMES` and the `StateClassifier` into a display loop that updates the `#cat-screen` element independently of the slower 10-second game tick.

## Acceptance Criteria
- [ ] `AnimationRenderer.start()` begins the animation loop using `setInterval` at a 250 ms interval (4 FPS).
- [ ] Each interval, `AnimationRenderer` calls `StateClassifier.classify()` to determine the current state, then toggles the frame index (0 → 1 → 0 → …) and sets `document.getElementById('cat-screen').textContent` to the corresponding frame string from `CAT_FRAMES`.
- [ ] Frame index resets to 0 whenever the derived state changes (state transition).
- [ ] `AnimationRenderer.stop()` clears the interval (used when the name-prompt overlay is visible and the game hasn't started yet).
- [ ] The animation loop does NOT run before the game is initialised (i.e., before the player submits a name or a cookie is loaded).

## Implementation Hints
- Track the previous state in a module-level variable. On each tick, compare `newState !== prevState` to detect a transition and reset frame index.
- `setInterval` with 250 ms is simpler and more than adequate; `requestAnimationFrame` is not required here (the design permits either).
- The `#cat-screen` `<pre>` element must have a fixed character width (established in STORY-001 CSS) so frame switching never causes layout reflow.

## Test Requirements
- After game init, the `#cat-screen` element alternates between two different strings every ~250 ms for the `idle` state (observable via browser console `setInterval` patch or visual inspection).
- Manually call `GameState.isDead = true` in console → screen transitions to the `dead` frames within ~250 ms.
- Manually set `ActionHandler.transientState = 'eating'; ActionHandler.transientUntil = Date.now() + 2000` → screen shows eating frames, then reverts to idle after 2 s.
- `AnimationRenderer.stop()` halts the interval; no further `#cat-screen` updates occur.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
