#!/usr/bin/env bash
# test_helper.bash — shared BATS setup/teardown and fixture utilities
# Loaded by reset-stories.bats via:  load 'test_helper'
#
# Implements:
#   setup              — called automatically before each @test
#   teardown           — called automatically after each @test
#   make_story_fixture — helper to create a story file in the fixture tree

# ---------------------------------------------------------------------------
# setup — called automatically before each @test
# ---------------------------------------------------------------------------
setup() {
  # Create a temporary directory for this test
  TEST_DIR=$(mktemp -d)
  export TEST_DIR

  # Create the required subdirectories
  mkdir -p "$TEST_DIR/stories"
  mkdir -p "$TEST_DIR/workspace"

  # Set the path to the script under test (from the tests/ subdirectory)
  export SCRIPT_UNDER_TEST="${BATS_TEST_DIRNAME}/../reset-stories.sh"
}

# ---------------------------------------------------------------------------
# teardown — called automatically after each @test
# ---------------------------------------------------------------------------
teardown() {
  # Remove the temporary directory and all its contents
  rm -rf "$TEST_DIR"
}

# ---------------------------------------------------------------------------
# make_story_fixture — create an empty story file in the fixture directory
# Usage: make_story_fixture <dir> <filename>
# Example: make_story_fixture "$TEST_DIR" "STORY-001.md"
# ---------------------------------------------------------------------------
make_story_fixture() {
  local fixture_dir="$1"
  local filename="$2"

  # Create an empty file in the stories/ subdirectory
  touch "$fixture_dir/stories/$filename"
}
