#!/usr/bin/env bash
# test_helper.bash — shared BATS setup / teardown helpers
#
# Source this file at the top of every BATS test file:
#   load 'test_helper'

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# Absolute path to the workspace root (one level above tests/)
WORKSPACE_DIR="$(cd "$(dirname "${BATS_TEST_FILENAME}")/.." && pwd)"

# Absolute path to the script under test
SCRIPT="$WORKSPACE_DIR/reset-stories.sh"

# ---------------------------------------------------------------------------
# BATS setup / teardown hooks
# ---------------------------------------------------------------------------

# setup
#   Called automatically by BATS before each @test.
#   Creates a temporary directory that mimics the momo-agents project root.
#   Sets global variables:
#     TEST_DIR      — the temp project root
#     SCRIPT_UNDER_TEST — absolute path to reset-stories.sh
setup() {
    TEST_DIR="$(mktemp -d)"
    mkdir -p "$TEST_DIR/stories"
    mkdir -p "$TEST_DIR/workspace"

    SCRIPT_UNDER_TEST="$(cd "$(dirname "${BATS_TEST_FILENAME}")/.." && pwd)/reset-stories.sh"
    export TEST_DIR SCRIPT_UNDER_TEST
}

# teardown
#   Called automatically by BATS after each @test.
#   Removes the temporary directory created by setup.
teardown() {
    [[ -n "${TEST_DIR:-}" ]] && rm -rf "$TEST_DIR"
}

# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

# make_story_fixture <dir> <filename>
#   Creates an empty file at <dir>/stories/<filename>.
#   Used to seed story files in various states during tests.
make_story_fixture() {
    local dir="$1"
    local filename="$2"
    touch "$dir/stories/$filename"
}

# ---------------------------------------------------------------------------
# Legacy fixture helpers (for backward compatibility)
# ---------------------------------------------------------------------------

# setup_fixture_dir <dir>
#   Creates a temporary directory that mimics the momo-agents project root.
#   Sets global variables:
#     FIXTURE_ROOT  — the temp project root
#     FIXTURE_STORIES    — stories/ sub-directory
#     FIXTURE_WORKSPACE  — workspace/ sub-directory
setup_fixture_dir() {
    FIXTURE_ROOT="$(mktemp -d)"
    FIXTURE_STORIES="$FIXTURE_ROOT/stories"
    FIXTURE_WORKSPACE="$FIXTURE_ROOT/workspace"

    mkdir -p "$FIXTURE_STORIES"
    mkdir -p "$FIXTURE_WORKSPACE"
}

# teardown_fixture_dir
#   Removes the temporary directory created by setup_fixture_dir.
teardown_fixture_dir() {
    [[ -n "${FIXTURE_ROOT:-}" ]] && rm -rf "$FIXTURE_ROOT"
}

# run_script [args...]
#   Runs reset-stories.sh from within FIXTURE_ROOT, forwarding any extra
#   arguments.  Uses 'bats run' so exit codes and output are captured.
#
# Note: the script derives paths relative to SCRIPT_DIR (its own location).
# Tests therefore symlink or copy the script into FIXTURE_ROOT.
run_script() {
    # Copy script into the fixture root so SCRIPT_DIR resolves correctly.
    cp "$SCRIPT" "$FIXTURE_ROOT/reset-stories.sh"
    chmod +x "$FIXTURE_ROOT/reset-stories.sh"

    run bash "$FIXTURE_ROOT/reset-stories.sh" "$@"
}
