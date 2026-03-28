# STORY-002: easy CookieManager Module

**Index**: 2
**Complexity**: easy
**Attempts**: 1
**Design ref**: design/virtual-cat-pet.new.md
**Depends on**: STORY-001

## Context
All game state must survive tab/browser close. The CookieManager is a small utility that serialises and deserialises the `vcat_state` cookie. It is the only I/O layer — all other components read from and write to an in-memory object; they call CookieManager to persist changes.

## Acceptance Criteria
- [ ] A `CookieManager` object (or set of functions) is defined in an inline `<script>` block in `virtual-cat-pet.html`.
- [ ] `CookieManager.save(stateObj)` serialises `stateObj` to a URI-encoded JSON string and writes it as the `vcat_state` cookie with an `expires` attribute set to 365 days from the current date.
- [ ] `CookieManager.load()` reads the `vcat_state` cookie, URI-decodes it, JSON-parses it, and returns the parsed object.
- [ ] If the cookie is absent, `CookieManager.load()` returns `null`.
- [ ] If the cookie value is present but JSON-malformed (corrupt), `CookieManager.load()` catches the error with `try/catch` and returns `null` (graceful degradation).
- [ ] The saved cookie value stays within ~512 bytes for the nominal state object (enforced by keeping only the fields defined in the data model).
- [ ] `CookieManager.clear()` deletes the `vcat_state` cookie by setting its `expires` to a past date (used for resurrection / reset flows).

## Implementation Hints
- Use `document.cookie` directly — no external libraries.
- For reading: split `document.cookie` on `'; '`, find the entry starting with `vcat_state=`, then `decodeURIComponent` the value portion.
- For writing: `document.cookie = \`vcat_state=${encodeURIComponent(JSON.stringify(state))}; expires=${date.toUTCString()}; path=/\``.
- Keep this module pure (no DOM access, no game-logic knowledge) so it is easy to unit-test in isolation.

## Test Requirements
- Call `CookieManager.save({ name: "Test", hunger: 50 })` in the browser console and verify `document.cookie` contains `vcat_state`.
- Call `CookieManager.load()` and confirm it returns the object saved above.
- Manually corrupt the cookie value (set it to `vcat_state=!!!`) and confirm `CookieManager.load()` returns `null` without throwing.
- Call `CookieManager.clear()` and confirm `CookieManager.load()` subsequently returns `null`.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
