# STORY-004: easy ASCII Cat Art Frames

**Index**: 4
**Complexity**: easy
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-001

## Context
The visual heart of the game is the animated ASCII/Unicode pixel cat. All eight animation states need exactly two frames each, defined as plain multi-line string constants. This story is purely additive — no logic, no DOM manipulation — and the frames can be written in parallel with other stories.

## Acceptance Criteria
- [ ] A `CAT_FRAMES` constant (object or Map) is defined in the inline `<script>` block.
- [ ] The following eight state keys exist: `idle`, `hungry`, `unhappy`, `sick`, `eating`, `playing`, `sleeping`, `dead`.
- [ ] Each key maps to an array of exactly **2** strings (frame 0 and frame 1).
- [ ] Every frame is a multi-line string drawn on an approximately 12-column × 8-row character grid so all frames are the same bounding-box size (prevents layout reflow during animation).
- [ ] Frames visually communicate the cat's state using ASCII/Unicode characters (no image files):
  - `idle` — sitting cat; tail position differs between frames (left / right sway).
  - `hungry` — cat looking upward with an empty bowl visible.
  - `unhappy` — cat with drooping ears or sad expression between frames.
  - `sick` — cat lying down; wavy lines (`~` or `≈`) above it alternate position.
  - `eating` — cat at a bowl; head dips down in frame 1.
  - `playing` — cat batting a small ball; ball position left in frame 0, right in frame 1.
  - `sleeping` — cat curled up; `z`, `z Z` or `z z Z` alternates between frames.
  - `dead` — cat on its back; `×` eyes, no movement needed (both frames may be identical or subtly differ).
- [ ] Each frame string uses a fixed-width character set so the `<pre>` element renders it without wrapping.

## Implementation Hints
- Define as a JS object literal: `const CAT_FRAMES = { idle: ["frame0string", "frame1string"], ... }`.
- Pad shorter rows with spaces to keep a uniform width across all frames — this prevents the `<pre>` from changing width as frames cycle.
- Use Unicode box-drawing or block characters (`▄ ▀ █ ░`) plus standard ASCII symbols (`^ v ( ) ~ _ /`) for the cat shape.
- "Dead" frames can be identical; the animation loop will still toggle between them without visual effect.

## Test Requirements
- `CAT_FRAMES` is accessible in the browser console without errors.
- All 8 keys are present: `Object.keys(CAT_FRAMES).sort()` matches the expected list.
- Each value is an array of length 2 where both elements are non-empty strings.
- Manually setting `document.getElementById('cat-screen').textContent = CAT_FRAMES.idle[0]` renders a recognisable cat shape in the browser (visual inspection).
- All frames for all states render without changing the width of the `#cat-screen` element (visual inspection for layout stability).

---
<!-- Coding Agent appends timestamped failure notes below this line -->
