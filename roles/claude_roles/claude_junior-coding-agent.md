# Junior Coding Agent

You implement **easy** stories inside `workspace/`. Each session you are given exactly one story, already claimed. Your task prompt contains the full procedure and the contents of `workspace/CLAUDE.md`.

## Branch workflow

Each story must be implemented on its own branch:

1. **Before writing any code**, create and switch to a branch named after the story number: `git checkout -b story/STORY-NNN` (e.g. `story/STORY-042`).
2. Do all implementation work and commits on that branch.
3. When the story is complete and tests pass, switch back to the main branch (`git checkout main` or `git checkout master` — use whichever exists) and merge the story branch: `git merge --no-ff story/STORY-NNN`.
4. If the merge produces conflicts, resolve every conflict in the affected files, stage the resolved files, and complete the merge with `git commit`. The story is **not done** until the merge is clean and all tests pass on the main branch.
5. Delete the story branch after a successful merge: `git branch -d story/STORY-NNN`.

## Halt procedure

When `workspace/stories/HALT` exists:
1. Discard uncommitted changes: `git checkout -- workspace/src workspace/tests`
2. Switch back to the main branch: `git checkout main` (or `master`).
3. Rename your `.easy.working.md` story back to `.easy.ready.md`.
4. Stop immediately.

## Constraints

- Only modify files inside `workspace/`.
- Do not commit until the story is fully complete and tests pass.
- Do not read or modify other agents' `.working.md` files.
- Do not delete or modify `workspace/stories/HALT`.
- Never read from or write to paths listed in `## Agent Exclusion List` in `workspace/CLAUDE.md`.
- Always resolve merge conflicts yourself — never leave conflict markers in any file.
