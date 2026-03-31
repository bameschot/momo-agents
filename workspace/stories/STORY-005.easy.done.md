# STORY-005: easy Card Limit & Cookie Size Warnings

**Index**: 5
**Complexity**: easy
**Design ref**: workspace/design/kanban-board.processed.md | workspace/design/kanban-board.new.md
**Depends on**: STORY-003

## Context
Adds two safety warnings to protect users from hitting browser cookie limits. A dismissible banner alerts when the total card count exceeds 20, and a separate inline message warns when the serialised cookie payload nears the 4 KB browser limit. Both warnings are driven entirely by `saveState()` so they fire automatically on every mutation.

## Acceptance Criteria
- [ ] After every call to `saveState(state)`, the total card count across all three columns is computed.
- [ ] If the total card count exceeds **20**, the warning banner element (already present in the DOM from STORY-001) becomes visible, displaying the message: *"You have more than 20 cards — cookie storage may be limited."*
- [ ] The warning banner includes a dismiss ("×") button. Clicking it hides the banner for the current session (the banner is not shown again until the next `saveState` call that still finds count > 20, meaning it reappears if the user adds another card while still over the limit).
- [ ] When the total card count drops back to **20 or fewer**, the warning banner is hidden automatically by the next `saveState` call — no manual dismissal required.
- [ ] After every `saveState(state)` call, the byte length of the serialised JSON is checked. If it exceeds **3 800 bytes**, an additional warning message (distinct from the card-count banner, e.g. an inline paragraph below the board) is shown: *"Cookie storage is nearly full. Remove some cards to avoid data loss."*
- [ ] The cookie size warning disappears automatically when the payload drops back to 3 800 bytes or fewer.
- [ ] Neither warning is shown on initial page load if the conditions are not met.

## Implementation Hints
- Centralise both checks in a `checkWarnings(state, serialisedJson)` function called at the end of `saveState`. Pass the already-serialised string so you avoid double-serialising.
- Byte length: `new Blob([serialisedJson]).size` gives the accurate UTF-8 byte count (important if card text contains non-ASCII characters); `serialisedJson.length` is a safe approximation for ASCII-only content and simpler to implement.
- The banner dismiss sets a module-level `bannerDismissed` flag. `checkWarnings` skips showing the banner if `bannerDismissed` is `true` AND the count is still the same or lower than when dismissed. Reset the flag if the count increases (a new card was added).
- Simpler alternative: reset `bannerDismissed = false` on every `saveState` call, then check it in order: if count > 20 and not dismissed → show banner. This means the banner reappears after every new save if still over 20 and not dismissed in this call cycle — which is acceptable per the design.
- The cookie size warning element can be a `<p id="cookie-size-warning">` placed just below the `.board` container; toggle `hidden` attribute or a CSS class.
- Ensure warning elements have `role="alert"` or `aria-live="polite"` so screen readers announce them.

## Test Requirements
- Adding a 21st card triggers the card-count warning banner. Clicking "×" dismisses it. Deleting a card (dropping count to 20) hides the banner automatically.
- Filling cards with long descriptions until the serialised JSON exceeds 3 800 bytes causes the cookie size warning to appear. Deleting cards until the payload is back under 3 800 bytes makes the warning disappear.
- On fresh page load with fewer than 20 cards and a small cookie payload, neither warning is visible.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
