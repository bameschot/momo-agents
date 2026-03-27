#!/usr/bin/env bash
# reset-team.sh — wipes all generated artefacts and resets the repo to a clean
# state so the team can start a completely fresh run.
#
# What gets removed:
#   stories/    — all story files (STORY-*.md in every state)
#   design/     — all design documents
#   .sentinels/ — all orchestrator sentinel files
#   workspace/  — all generated source code and tests
#                 (CLAUDE.md and the src/ + tests/ skeleton are preserved)
#
# Usage: ./reset-team.sh [--yes]
#   --yes   Skip the confirmation prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STORIES_DIR="$SCRIPT_DIR/stories"
DESIGN_DIR="$SCRIPT_DIR/design"
SENTINEL_DIR="$SCRIPT_DIR/.sentinels"
WORKSPACE_DIR="$SCRIPT_DIR/workspace"

# ─────────────────────────────────────────────────────────────────────────────
# Confirmation
# ─────────────────────────────────────────────────────────────────────────────
AUTO_YES=false
for arg in "$@"; do
    [[ "$arg" == "--yes" ]] && AUTO_YES=true
done

echo "╔══════════════════════════════════════════════════╗"
echo "║           momo-agents  ·  reset-team             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  This will permanently delete:"
echo "    • All story files in       stories/"
echo "    • All design documents in  design/"
echo "    • All sentinel files in    .sentinels/"
echo "    • All generated code in    workspace/  (CLAUDE.md preserved)"
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

# ─────────────────────────────────────────────────────────────────────────────
# Stories
# ─────────────────────────────────────────────────────────────────────────────
if compgen -G "$STORIES_DIR/STORY-*.md"       > /dev/null 2>&1 || \
   compgen -G "$STORIES_DIR/STORY-*.working.md" > /dev/null 2>&1 || \
   compgen -G "$STORIES_DIR/STORY-*.done.md"    > /dev/null 2>&1 || \
   compgen -G "$STORIES_DIR/STORY-*.failed.md"  > /dev/null 2>&1 || \
   [ -f "$STORIES_DIR/HALT" ]; then
    rm -f "$STORIES_DIR"/STORY-*.md \
          "$STORIES_DIR"/STORY-*.working.md \
          "$STORIES_DIR"/STORY-*.done.md \
          "$STORIES_DIR"/STORY-*.failed.md \
          "$STORIES_DIR"/STORY-*.reviewing.md \
          "$STORIES_DIR/HALT"
    echo "  ✓ stories/     cleared"
else
    echo "  – stories/     already empty"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Designs
# ─────────────────────────────────────────────────────────────────────────────
if compgen -G "$DESIGN_DIR/*.md" > /dev/null 2>&1; then
    rm -f "$DESIGN_DIR"/*.md
    echo "  ✓ design/      cleared"
else
    echo "  – design/      already empty"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Sentinels
# ─────────────────────────────────────────────────────────────────────────────
if [ -d "$SENTINEL_DIR" ] && [ "$(ls -A "$SENTINEL_DIR" 2>/dev/null)" ]; then
    rm -rf "$SENTINEL_DIR"
    echo "  ✓ .sentinels/  cleared"
else
    echo "  – .sentinels/  already empty"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Workspace — remove generated files, preserve CLAUDE.md + skeleton dirs
# ─────────────────────────────────────────────────────────────────────────────
ws_cleared=false
if [ -d "$WORKSPACE_DIR" ]; then
    # Remove everything except CLAUDE.md, then recreate skeleton dirs
    find "$WORKSPACE_DIR" -mindepth 1 \
        ! -name "CLAUDE.md" \
        ! -path "$WORKSPACE_DIR/src" \
        ! -path "$WORKSPACE_DIR/src/.gitkeep" \
        ! -path "$WORKSPACE_DIR/tests" \
        ! -path "$WORKSPACE_DIR/tests/.gitkeep" \
        -delete 2>/dev/null || true

    # Ensure skeleton dirs exist with their .gitkeep
    mkdir -p "$WORKSPACE_DIR/src" "$WORKSPACE_DIR/tests"
    touch "$WORKSPACE_DIR/src/.gitkeep" "$WORKSPACE_DIR/tests/.gitkeep"

    ws_cleared=true
    echo "  ✓ workspace/   cleared  (CLAUDE.md + src/ + tests/ preserved)"
else
    echo "  – workspace/   does not exist (nothing to clear)"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║          Reset complete — ready to go  🧹        ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Run './start-team.sh <feature-name>' to start a fresh session."
echo ""
