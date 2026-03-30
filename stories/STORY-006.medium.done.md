# STORY-006: medium BATS Test Suite

**Index**: 6
**Complexity**: medium
**Design ref**: design/reset-stories.new.md
**Depends on**: STORY-004, STORY-005

## Context
Every component of `reset-stories.sh` must be covered by automated BATS tests so regressions are caught immediately. The tests run against the real script (not a mock) using an isolated temporary directory produced by the helper. The suite must cover the story renamer, HALT cleaner, workspace cleaner, `--yes` flag, interactive cancellation, and idempotency behaviour.

## Acceptance Criteria
- [ ] File `workspace/tests/reset-stories.bats` exists and is a valid BATS file.
- [ ] `load 'test_helper'` is present at the top of the file to pull in shared fixtures.
- [ ] The following test cases are implemented (one `@test` per case, descriptive names):

  **Story renamer**
  - [ ] A `STORY-NNN.easy.done.md` file is renamed to `STORY-NNN.md`.
  - [ ] A `STORY-NNN.medium.working.md` file is renamed to `STORY-NNN.md`.
  - [ ] A `STORY-NNN.hard.failed.md` file is renamed to `STORY-NNN.md`.
  - [ ] A `STORY-NNN.easy.reviewing.md` file is renamed to `STORY-NNN.md`.
  - [ ] A `STORY-NNN.medium.ready.md` file is renamed to `STORY-NNN.md`.
  - [ ] An already-bare `STORY-NNN.md` file is left untouched.
  - [ ] Running the script twice (idempotency) succeeds and leaves all files bare.

  **HALT cleaner**
  - [ ] `stories/HALT` is removed when present.
  - [ ] Script exits `0` when `stories/HALT` is absent.
  - [ ] Output contains `✓ HALT removed` when HALT was present.
  - [ ] Output contains `–` HALT line when HALT was absent.

  **Workspace cleaner**
  - [ ] All files inside `workspace/` are deleted when workspace has contents.
  - [ ] The `workspace/` directory itself is preserved after clearing.
  - [ ] An empty `workspace/` produces `–` (already empty) output, no error.

  **`--yes` flag**
  - [ ] Script completes without prompting when invoked with `--yes`.

  **Cancellation**
  - [ ] Entering `n` at the prompt exits `0` and prints `Reset cancelled.`.
  - [ ] Pressing Enter (empty input) at the prompt exits `0` without performing any actions.

  **Summary output**
  - [ ] Output includes `renamed N stories` where N matches the number of state-encoded files.
  - [ ] Closing banner text `Reset complete` is present in output.

- [ ] All tests pass: `bats workspace/tests/reset-stories.bats` exits `0`.
- [ ] `shellcheck workspace/tests/reset-stories.bats workspace/tests/test_helper.bash` exits `0`.

## Implementation Hints
- Invoke the script with `run bash "$SCRIPT_UNDER_TEST" --yes` or pipe `printf 'y\n'` to its stdin for interactive tests: `run bash "$SCRIPT_UNDER_TEST" <<< 'y'`.
- For cancellation tests, pipe `n` or an empty string: `run bash "$SCRIPT_UNDER_TEST" <<< ''`.
- BATS `assert_output --partial "text"` (from bats-support/bats-assert) or plain `[[ "$output" == *"text"* ]]` both work — use whichever is available.
- Override `STORIES_DIR` and `WORKSPACE_DIR` by passing them as env vars if the script supports it, or by setting up the fixture under the same relative paths the script expects (run the script from `$TEST_DIR`).
- The cleanest approach: create the fixture tree inside `$TEST_DIR`, copy `reset-stories.sh` there (or symlink it), then `run bash reset-stories.sh --yes` with `cd "$TEST_DIR"` — this avoids the need to parameterise path variables inside the script.
- All test state must be confined to `$TEST_DIR`; never mutate the real `stories/` or `workspace/` directories.

## Test Requirements
- The tests **are** the test requirements for this story.
- Edge case: a `stories/` directory that contains only bare files (no state-encoded files) — `renamed_count` should be `0` and the `–` summary line should appear.
- Edge case: `workspace/` containing nested subdirectories — all must be deleted.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
