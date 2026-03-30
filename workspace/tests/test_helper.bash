#!/usr/bin/env bash
set -euo pipefail
# tests/test_helper.bash — shared BATS setup/teardown and fixture helpers
# Loaded by reset-stories.bats via:  load 'test_helper'
#
# Provides:
#   $TEST_DIR            — temporary directory created fresh for each test
#   $SCRIPT_UNDER_TEST   — absolute path to ../reset-stories.sh
#   make_story_fixture() — creates an empty story file in $TEST_DIR/stories/

# setup is called before each @test block
setup() {
    # Create a temporary directory for this test
    TEST_DIR=$(mktemp -d)

    # Create required subdirectories
    mkdir -p "$TEST_DIR/stories"
    mkdir -p "$TEST_DIR/workspace"

    # Locate the script under test
    # BATS_TEST_DIRNAME is the directory of the .bats file (workspace/tests/)
    # We need to go up and find reset-stories.sh in the project root
    SCRIPT_UNDER_TEST="$(cd "$BATS_TEST_DIRNAME/.." && pwd)/reset-stories.sh"

    # Export variables so they're available to tests
    export TEST_DIR
    export SCRIPT_UNDER_TEST
}

# teardown is called after each @test block
teardown() {
    # Clean up the temporary directory
    rm -rf "$TEST_DIR"
}

# make_story_fixture - creates an empty story file for testing
# Usage: make_story_fixture <dir> <filename>
# Example: make_story_fixture "$TEST_DIR" "STORY-001.easy.ready.md"
make_story_fixture() {
    local dir="$1"
    local filename="$2"

    touch "$dir/stories/$filename"
}
