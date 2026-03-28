# STORY-005: medium DecayEngine — Stat Decay & Offline Catch-Up

**Index**: 5
**Complexity**: medium
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-003

## Context
Stats degrade over real time whether the tab is open or not. The DecayEngine must apply the correct amount of decay both on each live 10-second tick and in a single catch-up calculation when the page reloads after the tab was closed. Getting the maths right here is critical to the game feeling fair.

## Acceptance Criteria
- [ ] A `DecayEngine` object with a `tick(elapsedMs)` method is defined.
- [ ] `tick(elapsedMs)` applies decay to the in-memory `GameState` for the given elapsed milliseconds, using the base rates from the design:
  - Hunger: −1 pt per 4 minutes (−1 pt per 240 000 ms).
  - Happiness: −1 pt per 6 minutes (−1 pt per 360 000 ms).
  - Health: −1 pt per 8 minutes (−1 pt per 480 000 ms) — **only** when `GameState.hunger < 20` OR `GameState.happiness < 20`.
  - Age: +1 day per 1 real hour (+1 per 3 600 000 ms).
- [ ] Each computed delta (for hunger and happiness) is multiplied by a jitter factor in the range `[0.8, 1.2]` (±20 % random). Age and health use no jitter.
- [ ] All stats are clamped to their valid ranges after decay: hunger/happiness/health ∈ [0, 100], age ≥ 0.
- [ ] If `GameState.isDead`, `tick()` returns immediately without modifying any stats.
- [ ] `DecayEngine.catchUp()` reads `GameState.lastTick`, computes `now - lastTick` as elapsed, calls `tick(elapsed)`, then updates `GameState.lastTick = Date.now()`.
- [ ] `DecayEngine.catchUp()` is called once during page-load initialisation (after `GameState.init()`).
- [ ] After each live tick, `GameState.lastTick` is updated to `Date.now()` and `GameState.save()` is called.

## Implementation Hints
- Convert elapsed ms to fractional "ticks" for each stat: `delta = (elapsedMs / rateMs) * baseDecrement`.
- For offline catch-up, run the full elapsed time through a single `tick()` call rather than simulating N individual ticks — this keeps computation O(1) regardless of how long the tab was closed.
- Apply jitter only to hunger and happiness (as per design); health decay is deterministic.
- Guard against negative elapsed (clock skew or cookie tamper): if `elapsedMs < 0`, treat it as 0.
- Cap offline catch-up at a maximum of 7 days (604 800 000 ms) to prevent a cat from instantly dying after a very long absence — this is a reasonable UX decision not explicitly in the design but implied by fair gameplay.

## Test Requirements
- Call `DecayEngine.tick(240000)` with full stats → hunger decreases by approximately 1 pt (within ±20 % jitter), happiness unchanged (6-min rate not reached), health unchanged (no critical low stats).
- Call `DecayEngine.tick(3600000)` → age increases by exactly 1.
- Set `GameState.hunger = 15`, call `DecayEngine.tick(480000)` → health decreases by approximately 1 pt.
- Set `GameState.hunger = 50`, `GameState.happiness = 50`, call `DecayEngine.tick(480000)` → health unchanged.
- Set `GameState.isDead = true`, call `DecayEngine.tick(999999)` → no stats change.
- Set `GameState.lastTick` to 30 minutes ago, call `DecayEngine.catchUp()` → hunger reduced by ~7–8 pts (30 min / 4 min × ±20% jitter).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
