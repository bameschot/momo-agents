#!/usr/bin/env bash
# reset-stories.sh — resets story files to a clean state.
#
# Usage: ./reset-stories.sh [--yes]
#   --yes   Skip the confirmation prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export STORIES_DIR="$SCRIPT_DIR/stories"
export WORKSPACE_DIR="$SCRIPT_DIR/workspace"

# ─────────────────────────────────────────────────────────────────────────────
# Argument Parsing
# ─────────────────────────────────────────────────────────────────────────────
export AUTO_YES=false
for arg in "$@"; do
    [[ "$arg" == "--yes" ]] && AUTO_YES=true
done
