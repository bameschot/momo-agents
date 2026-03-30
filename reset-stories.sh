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

# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Banner
# ─────────────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║         momo-agents  ·  reset-stories            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  This will:"
echo "    • Rename all state-encoded story files → bare STORY-NNN.md form"
echo "    • Remove stories/HALT sentinel (if present)"
echo "    • Clear all generated content in  workspace/"
echo ""

if [ "$AUTO_YES" = false ]; then
    read -r -p "  Are you sure? [y/N] " answer
    case "$answer" in
        [yY][eE][sS]|[yY]) ;;
        *)
            echo ""
            echo "  Reset cancelled."
            exit 0
            ;;
    esac
fi

echo ""
