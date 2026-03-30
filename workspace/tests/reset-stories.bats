#!/usr/bin/env bats
# reset-stories.bats — BATS test suite for reset-stories.sh
#
# Run with:   bats tests/
#         or: bats tests/reset-stories.bats

load 'test_helper'

# ---------------------------------------------------------------------------
# Setup / teardown
# ---------------------------------------------------------------------------

setup() {
    setup_fixture_dir
}

teardown() {
    teardown_fixture_dir
}

# ---------------------------------------------------------------------------
# Helper: create a state-encoded story file in the fixture stories/ dir
# ---------------------------------------------------------------------------
create_story() {
    # create_story <filename>   e.g. "STORY-001.easy.done.md"
    touch "$FIXTURE_STORIES/$1"
}

# ---------------------------------------------------------------------------
# 1. Story Renamer — state-encoded files are renamed to bare form
# ---------------------------------------------------------------------------

@test "renames easy.done story to bare form" {
    create_story "STORY-001.easy.done.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-001.md" ]
    [ ! -f "$FIXTURE_STORIES/STORY-001.easy.done.md" ]
}

@test "renames medium.working story to bare form" {
    create_story "STORY-002.medium.working.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-002.md" ]
    [ ! -f "$FIXTURE_STORIES/STORY-002.medium.working.md" ]
}

@test "renames hard.failed story to bare form" {
    create_story "STORY-003.hard.failed.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-003.md" ]
    [ ! -f "$FIXTURE_STORIES/STORY-003.hard.failed.md" ]
}

@test "renames easy.reviewing story to bare form" {
    create_story "STORY-004.easy.reviewing.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-004.md" ]
    [ ! -f "$FIXTURE_STORIES/STORY-004.easy.reviewing.md" ]
}

@test "renames medium.ready story to bare form" {
    create_story "STORY-005.medium.ready.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-005.md" ]
    [ ! -f "$FIXTURE_STORIES/STORY-005.medium.ready.md" ]
}

@test "leaves already-bare story file untouched" {
    create_story "STORY-006.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-006.md" ]
}

@test "renames multiple state-encoded stories in one run" {
    create_story "STORY-001.easy.done.md"
    create_story "STORY-002.medium.working.md"
    create_story "STORY-003.hard.failed.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-001.md" ]
    [ -f "$FIXTURE_STORIES/STORY-002.md" ]
    [ -f "$FIXTURE_STORIES/STORY-003.md" ]
}

# ---------------------------------------------------------------------------
# 2. HALT Cleaner
# ---------------------------------------------------------------------------

@test "removes HALT sentinel when present" {
    touch "$FIXTURE_STORIES/HALT"
    run_script --yes
    [ "$status" -eq 0 ]
    [ ! -f "$FIXTURE_STORIES/HALT" ]
}

@test "succeeds without error when HALT is absent" {
    run_script --yes
    [ "$status" -eq 0 ]
}

@test "output contains HALT removed message when HALT was present" {
    touch "$FIXTURE_STORIES/HALT"
    run_script --yes
    [ "$status" -eq 0 ]
    [[ "$output" == *"HALT removed"* ]]
}

@test "output contains dash HALT line when HALT was absent" {
    run_script --yes
    [ "$status" -eq 0 ]
    [[ "$output" == *"–"*"HALT"* ]]
}

# ---------------------------------------------------------------------------
# 3. Workspace Cleaner
# ---------------------------------------------------------------------------

@test "removes files inside workspace/ but keeps the directory" {
    touch "$FIXTURE_WORKSPACE/CLAUDE.md"
    mkdir -p "$FIXTURE_WORKSPACE/src"
    touch "$FIXTURE_WORKSPACE/src/main.sh"
    run_script --yes
    [ "$status" -eq 0 ]
    [ -d "$FIXTURE_WORKSPACE" ]
    [ ! -f "$FIXTURE_WORKSPACE/CLAUDE.md" ]
    [ ! -d "$FIXTURE_WORKSPACE/src" ]
}

@test "succeeds when workspace/ is already empty" {
    run_script --yes
    [ "$status" -eq 0 ]
    [ -d "$FIXTURE_WORKSPACE" ]
}

@test "empty workspace produces dash already-empty output line" {
    run_script --yes
    [ "$status" -eq 0 ]
    [[ "$output" == *"–"* ]]
}

# ---------------------------------------------------------------------------
# 4. --yes flag (non-interactive mode)
# ---------------------------------------------------------------------------

@test "--yes flag skips confirmation prompt" {
    # If the script hangs waiting for input this test will timeout, which
    # counts as a failure — so a successful exit proves --yes worked.
    run_script --yes
    [ "$status" -eq 0 ]
}

# ---------------------------------------------------------------------------
# 5. Interactive cancellation
# ---------------------------------------------------------------------------

@test "cancellation (answer 'n') exits 0 and makes no changes" {
    create_story "STORY-001.easy.done.md"
    touch "$FIXTURE_STORIES/HALT"

    # Feed 'n' to stdin so the script cancels
    cp "$SCRIPT" "$FIXTURE_ROOT/reset-stories.sh"
    chmod +x "$FIXTURE_ROOT/reset-stories.sh"
    run bash -c "echo 'n' | bash '$FIXTURE_ROOT/reset-stories.sh'"

    [ "$status" -eq 0 ]
    # Story must NOT have been renamed
    [ -f "$FIXTURE_STORIES/STORY-001.easy.done.md" ]
    # HALT must NOT have been removed
    [ -f "$FIXTURE_STORIES/HALT" ]
}

@test "cancellation (answer 'n') prints Reset cancelled" {
    cp "$SCRIPT" "$FIXTURE_ROOT/reset-stories.sh"
    chmod +x "$FIXTURE_ROOT/reset-stories.sh"
    run bash -c "echo 'n' | bash '$FIXTURE_ROOT/reset-stories.sh'"

    [ "$status" -eq 0 ]
    [[ "$output" == *"Reset cancelled"* ]]
}

@test "cancellation (empty enter) exits 0 without performing any actions" {
    create_story "STORY-001.easy.done.md"
    touch "$FIXTURE_STORIES/HALT"

    cp "$SCRIPT" "$FIXTURE_ROOT/reset-stories.sh"
    chmod +x "$FIXTURE_ROOT/reset-stories.sh"
    run bash -c "echo '' | bash '$FIXTURE_ROOT/reset-stories.sh'"

    [ "$status" -eq 0 ]
    # Story must NOT have been renamed
    [ -f "$FIXTURE_STORIES/STORY-001.easy.done.md" ]
    # HALT must NOT have been removed
    [ -f "$FIXTURE_STORIES/HALT" ]
}

# ---------------------------------------------------------------------------
# 6. Idempotency
# ---------------------------------------------------------------------------

@test "running twice produces the same clean state" {
    create_story "STORY-001.easy.done.md"
    touch "$FIXTURE_STORIES/HALT"
    touch "$FIXTURE_WORKSPACE/CLAUDE.md"

    run_script --yes
    [ "$status" -eq 0 ]

    # Second run — everything is already clean
    run_script --yes
    [ "$status" -eq 0 ]
    [ -f "$FIXTURE_STORIES/STORY-001.md" ]
    [ ! -f "$FIXTURE_STORIES/HALT" ]
    [ -d "$FIXTURE_WORKSPACE" ]
    [ ! -f "$FIXTURE_WORKSPACE/CLAUDE.md" ]
}

# ---------------------------------------------------------------------------
# 7. Output / summary lines
# ---------------------------------------------------------------------------

@test "output includes renamed N stories where N matches count of state-encoded files" {
    create_story "STORY-001.easy.done.md"
    create_story "STORY-002.medium.working.md"
    create_story "STORY-003.hard.failed.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [[ "$output" == *"renamed 3"* ]]
}

@test "output contains workspace-cleared confirmation" {
    touch "$FIXTURE_WORKSPACE/CLAUDE.md"
    run_script --yes
    [ "$status" -eq 0 ]
    [[ "$output" == *"workspace"* ]]
}

@test "output contains Reset complete closing banner" {
    run_script --yes
    [ "$status" -eq 0 ]
    [[ "$output" == *"Reset complete"* ]]
}
