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

echo "╔═══════════════════════════════════════════════════════╗"
echo "║          momo-agents  ·  reset-stories               ║"
echo "╚═══════════════════════════════════════════════════════╝"
echo ""
echo "  This will:"
echo "    • Rename story files in       stories/"
echo "    • Remove                      stories/HALT"
echo "    • Delete all contents of      workspace/"
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
