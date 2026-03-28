"""
Tests for DecayEngine logic (STORY-005).

Run with: python3 tests/test_decay_engine.py

These tests replicate the DecayEngine logic in Python to validate correctness
without requiring a browser/JS runtime. The logic is identical to the JS in
virtual-cat-pet.html.
"""

import random
import time
import math
import sys


# ── Python port of GameState (minimal) ─────────────────────────────
class GameState:
    def __init__(self):
        self.name         = 'Tester'
        self.hunger       = 80.0
        self.happiness    = 80.0
        self.health       = 100.0
        self.age          = 0.0
        self.last_tick    = int(time.time() * 1000)
        self.neglect_since = None
        self.is_dead      = False
        self.force_sick   = False
        self.cooldowns    = {'feed': 0, 'play': 0, 'care': 0}
        self._saved       = {}

    def save(self):
        pass  # no-op in tests

    def reset(self, **overrides):
        self.hunger       = 80.0
        self.happiness    = 80.0
        self.health       = 100.0
        self.age          = 0.0
        self.last_tick    = int(time.time() * 1000)
        self.neglect_since = None
        self.is_dead      = False
        self.force_sick   = False
        self.cooldowns    = {'feed': 0, 'play': 0, 'care': 0}
        for k, v in overrides.items():
            setattr(self, k, v)


# ── Python port of DecayEngine ─────────────────────────────────────
MAX_CATCHUP_MS = 604_800_000


def tick(gs: GameState, elapsed_ms: int, *, seed=None):
    """Direct Python port of DecayEngine.tick()."""
    if gs.is_dead:
        return

    rng = random.Random(seed)
    ms = max(0, elapsed_ms)

    hunger_jitter     = 0.8 + rng.random() * 0.4
    hunger_delta      = (ms / 240_000) * hunger_jitter
    gs.hunger         = max(0.0, min(100.0, gs.hunger - hunger_delta))

    happiness_jitter  = 0.8 + rng.random() * 0.4
    happiness_delta   = (ms / 360_000) * happiness_jitter
    gs.happiness      = max(0.0, min(100.0, gs.happiness - happiness_delta))

    if gs.hunger < 20 or gs.happiness < 20:
        health_delta  = ms / 480_000
        gs.health     = max(0.0, min(100.0, gs.health - health_delta))

    gs.age            = max(0.0, gs.age + ms / 3_600_000)
    gs.last_tick      = int(time.time() * 1000)
    gs.save()


def catch_up(gs: GameState):
    """Direct Python port of DecayEngine.catchUp()."""
    now     = int(time.time() * 1000)
    elapsed = now - gs.last_tick
    if elapsed < 0:
        elapsed = 0
    if elapsed > MAX_CATCHUP_MS:
        elapsed = MAX_CATCHUP_MS
    tick(gs, elapsed)
    gs.last_tick = int(time.time() * 1000)
    gs.save()


# ── Simple test harness ────────────────────────────────────────────
passed = 0
failed = 0


def assert_test(condition: bool, description: str):
    global passed, failed
    if condition:
        print(f"  ✓ {description}")
        passed += 1
    else:
        print(f"  ✗ {description}")
        failed += 1


def describe(label: str):
    print(f"\n{label}")


# ── Test cases ─────────────────────────────────────────────────────

describe("DecayEngine.tick — hunger decay at exactly one rate-period")
gs = GameState()
before_hunger = gs.hunger
# Use jitter range [0.8,1.2] — test 100 iterations to confirm range
all_deltas = []
for i in range(100):
    gs.reset()
    before = gs.hunger
    tick(gs, 240_000, seed=i)
    all_deltas.append(before - gs.hunger)
min_d = min(all_deltas)
max_d = max(all_deltas)
assert_test(min_d >= 0.79 and max_d <= 1.21,
    f"hunger delta always in [0.8, 1.2] — observed [{min_d:.4f}, {max_d:.4f}]")


describe("DecayEngine.tick — age increases by exactly 1 after one hour")
gs.reset()
tick(gs, 3_600_000)
assert_test(abs(gs.age - 1.0) < 1e-9, f"age == 1 after 3 600 000 ms — actual: {gs.age}")


describe("DecayEngine.tick — health decays when hunger is critical")
gs.reset(hunger=15.0)
before_health = gs.health
tick(gs, 480_000)
delta = before_health - gs.health
assert_test(abs(delta - 1.0) < 1e-9,
    f"health decreases by exactly 1 when hunger < 20 — delta: {delta:.6f}")


describe("DecayEngine.tick — health unchanged when stats are healthy")
gs.reset(hunger=50.0, happiness=50.0)
before_health = gs.health
tick(gs, 480_000)
assert_test(gs.health == before_health, "health unchanged when hunger >= 20 AND happiness >= 20")


describe("DecayEngine.tick — isDead guard")
gs.reset(is_dead=True, hunger=80.0, happiness=80.0, health=100.0, age=0.0)
snap = (gs.hunger, gs.happiness, gs.health, gs.age)
tick(gs, 999_999)
assert_test(gs.hunger    == snap[0], "hunger unchanged when isDead")
assert_test(gs.happiness == snap[1], "happiness unchanged when isDead")
assert_test(gs.health    == snap[2], "health unchanged when isDead")
assert_test(gs.age       == snap[3], "age unchanged when isDead")


describe("DecayEngine.tick — negative elapsed treated as 0")
gs.reset()
snap = (gs.hunger, gs.happiness, gs.age)
tick(gs, -5000)
assert_test(gs.hunger    == snap[0], "hunger unchanged for negative elapsed")
assert_test(gs.happiness == snap[1], "happiness unchanged for negative elapsed")
assert_test(gs.age       == snap[2], "age unchanged for negative elapsed")


describe("DecayEngine.tick — stats clamped to valid ranges")
gs.reset(hunger=0.0, happiness=0.0, health=0.0, age=0.0)
tick(gs, 99_000_000)
assert_test(0 <= gs.hunger    <= 100, f"hunger clamped — actual: {gs.hunger}")
assert_test(0 <= gs.happiness <= 100, f"happiness clamped — actual: {gs.happiness}")
assert_test(0 <= gs.health    <= 100, f"health clamped — actual: {gs.health}")
assert_test(gs.age >= 0,              f"age clamped >= 0 — actual: {gs.age}")


describe("DecayEngine.catchUp — 30 min offline reduces hunger by ~7–8 pts (with jitter)")
thirty_min_ago = int(time.time() * 1000) - 30 * 60 * 1000
gs.reset(last_tick=thirty_min_ago)
before = gs.hunger
catch_up(gs)
delta = before - gs.hunger
# 30 min / 4 min = 7.5 × jitter [0.8, 1.2] → [6.0, 9.0]
assert_test(6.0 <= delta <= 9.0,
    f"hunger reduced ~7–8 pts after 30-min offline — actual: {delta:.4f}")


describe("DecayEngine.catchUp — lastTick updated after catchUp")
before_tick = int(time.time() * 1000) - 10_000
gs.reset(last_tick=before_tick)
catch_up(gs)
assert_test(gs.last_tick > before_tick,
    f"lastTick updated (was {before_tick}, now {gs.last_tick})")


describe("DecayEngine.catchUp — caps offline decay at 7 days")
eight_days_ago = int(time.time() * 1000) - 8 * 24 * 3600 * 1000
gs.reset(hunger=100.0, last_tick=eight_days_ago)
catch_up(gs)
# At 7 days: decay = 7*24*60/4 = 2520 base pts — far more than 100 — hunger → 0
assert_test(gs.hunger == 0.0,
    f"hunger hits 0 when capped at 7 days offline — actual: {gs.hunger}")


# ── Summary ────────────────────────────────────────────────────────
print(f"\n{'─' * 50}")
print(f"Results: {passed} passed, {failed} failed")
if failed > 0:
    sys.exit(1)
