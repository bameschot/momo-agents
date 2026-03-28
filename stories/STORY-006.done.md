# STORY-006: easy Neglect & Sickness Logic

**Index**: 6
**Complexity**: easy
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-005

## Context
Sustained neglect (low hunger or happiness for ≥ 120 minutes) triggers the sickness state. This logic is a discrete rule on top of the DecayEngine tick — it updates `neglectSince` and `forceSick` in GameState based on current stat values after each tick.

## Acceptance Criteria
- [ ] A `NeglectChecker.evaluate()` function (or method) is called after every `DecayEngine.tick()` invocation.
- [ ] If `GameState.hunger < 20` OR `GameState.happiness < 20` AND `GameState.neglectSince === null`, set `GameState.neglectSince = Date.now()`.
- [ ] If `GameState.hunger >= 20` AND `GameState.happiness >= 20`, reset `GameState.neglectSince = null` (critical threshold recovered before 120 min elapsed).
- [ ] If `neglectSince` is set and `Date.now() - neglectSince >= 7_200_000` ms (120 minutes), set `GameState.forceSick = true`.
- [ ] Once `forceSick` is set to `true`, it is **not** cleared by `NeglectChecker` — only the Care action (STORY-007) clears it.
- [ ] `NeglectChecker.evaluate()` does nothing if `GameState.isDead`.

## Implementation Hints
- Keep this as a pure function/method with no side-effects beyond mutating `GameState`; the caller is responsible for saving state.
- The 120-minute threshold is `120 * 60 * 1000 = 7_200_000` ms.
- `neglectSince` reset should only happen when **both** stats are ≥ 20 (i.e., fully out of the critical zone).

## Test Requirements
- With both stats above 20: `neglectSince` stays null, `forceSick` stays false.
- Set `GameState.hunger = 15`, call `NeglectChecker.evaluate()` → `neglectSince` is set to a recent timestamp.
- Call it again with hunger still < 20 → `neglectSince` does not advance (retains original value).
- Set `GameState.hunger = 50` (recovered), call `evaluate()` → `neglectSince` resets to null.
- Manually set `neglectSince` to 121 minutes ago, call `evaluate()` with hunger < 20 → `forceSick` becomes true.
- After `forceSick = true`: set `GameState.hunger = 80, happiness = 80`, call `evaluate()` → `neglectSince` resets but `forceSick` remains true (Care action needed).
- `GameState.isDead = true`: no changes occur.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
