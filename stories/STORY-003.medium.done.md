# STORY-003: medium Story Renamer

**Index**: 3
**Complexity**: medium
**Design ref**: design/reset-stories.new.md
**Depends on**: STORY-002

## Context
The primary purpose of `reset-stories.sh` is to rename state-encoded story files back to their bare BA-authored form. A story in progress might be named `STORY-002.medium.working.md`; after reset it must be `STORY-002.md`. Files already in bare form (`STORY-NNN.md`) must be left untouched so the operation is idempotent. The rename count is captured for the summary reporter added in STORY-004.

## Acceptance Criteria
- [ ] Iterates all files in `$STORIES_DIR/` whose names match the pattern `STORY-[0-9]+.(easy|medium|hard).(ready|working|done|failed|reviewing).md`.
- [ ] For each match, derives the bare name by extracting the `STORY-NNN` prefix (everything before the first `.`) and appending `.md`, then renames with `mv`.
- [ ] Already-bare `STORY-NNN.md` files are not touched (the glob simply doesn't match them).
- [ ] When at least one rename occurs, stores the count in a variable (e.g. `renamed_count`) for use by the summary reporter.
- [ ] When no state-encoded files exist, `renamed_count` is `0`.
- [ ] The section is idempotent: running it twice on the same directory produces the same result as running it once.
- [ ] `shellcheck reset-stories.sh` produces zero warnings.

## Implementation Hints
- Use a `for` loop over a glob: `for f in "$STORIES_DIR"/STORY-*.*.*.md; do … done`. Guard against no-match with `[[ -e "$f" ]] || continue`.
- Extract the bare name with bash parameter expansion: `bare="${f##*/}"` to get the filename, then `bare="STORY-${bare#STORY-}"` combined with cutting at the first dot: `prefix="${bare%%.*}"` → `"$STORIES_DIR/${prefix}.md"`.
- Alternatively, use `basename "$f"` then strip from the second token onwards with `${name%%.*}` to get `STORY-NNN`, then append `.md`.
- Do **not** use `sed`, `awk`, or `python` — only bash built-ins and POSIX utilities (`mv`, `basename`).
- A `compgen -G` pre-check (as in `reset-team.sh`) is not strictly needed here because the `for` loop guard handles the empty-glob case cleanly.

## Test Requirements
- BATS tests (STORY-006) must cover:
  - A mix of `done`, `working`, `failed`, `reviewing`, and `ready` state files all get renamed.
  - A bare `STORY-NNN.md` file is untouched.
  - Running the renamer twice (idempotency) leaves files in bare form without error.
  - The `renamed_count` variable reflects the correct number of files renamed.
  - Files in other directories (e.g. `workspace/`) are never touched.

---
<!-- Coding Agent appends timestamped failure notes below this line -->
