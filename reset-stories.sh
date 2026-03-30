#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC2034
STORIES_DIR="$SCRIPT_DIR/stories"
# shellcheck disable=SC2034
WORKSPACE_DIR="$SCRIPT_DIR/workspace"

# ─────────────────────────────────────────────────────────────────────────────
# Argument Parsing
# ─────────────────────────────────────────────────────────────────────────────
# shellcheck disable=SC2034
AUTO_YES=false
# shellcheck disable=SC2034
for arg in "$@"; do
    [[ "$arg" == "--yes" ]] && AUTO_YES=true
done
