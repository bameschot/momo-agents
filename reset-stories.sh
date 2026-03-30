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

# ─────────────────────────────────────────────────────────────────────────────
# Story Renamer — rename state-encoded files back to bare STORY-NNN.md form
# ─────────────────────────────────────────────────────────────────────────────
renamed_count=0
for f in "$STORIES_DIR"/STORY-*.*.*.md; do
    [[ -e "$f" ]] || continue
    filename="$(basename "$f")"
    prefix="${filename%%.*}"
    bare_name="${prefix}.md"
    mv "$f" "$STORIES_DIR/$bare_name"
    renamed_count=$(( renamed_count + 1 ))
done

if [[ "$renamed_count" -gt 0 ]]; then
    echo "  ✓ renamed $renamed_count stories"
else
    echo "  – stories/     already clean"
fi

# ─────────────────────────────────────────────────────────────────────────────
# HALT Cleaner — remove stories/HALT sentinel if present
# ─────────────────────────────────────────────────────────────────────────────
halt_was_present=false
if [ -f "$STORIES_DIR/HALT" ]; then
    halt_was_present=true
fi
rm -f "$STORIES_DIR/HALT"

# ─────────────────────────────────────────────────────────────────────────────
# Workspace Cleaner — remove all contents of workspace/ while keeping directory
# ─────────────────────────────────────────────────────────────────────────────
ws_was_empty=true
if [ -d "$WORKSPACE_DIR" ]; then
    if [ "$(find "$WORKSPACE_DIR" -mindepth 1 -type f 2>/dev/null | wc -l)" -gt 0 ] || \
       [ "$(find "$WORKSPACE_DIR" -mindepth 1 -type d 2>/dev/null | wc -l)" -gt 0 ]; then
        ws_was_empty=false
    fi
fi
if [ -d "$WORKSPACE_DIR" ] && [ "$ws_was_empty" = false ]; then
    find "$WORKSPACE_DIR" -mindepth 1 -delete
fi

# ─────────────────────────────────────────────────────────────────────────────
# Summary Reporter
# ─────────────────────────────────────────────────────────────────────────────
echo ""

if [ "$halt_was_present" = true ]; then
    echo "  ✓ HALT removed"
else
    echo "  – HALT         not present"
fi

if [ -d "$WORKSPACE_DIR" ]; then
    if [ "$ws_was_empty" = false ]; then
        echo "  ✓ workspace/   cleared"
    else
        echo "  – workspace/   already empty"
    fi
else
    echo "  – workspace/   does not exist (nothing to clear)"
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║       Reset complete — ready to go 🧹           ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Run './start-team.sh <feature-name>' to start a fresh session."
echo ""
