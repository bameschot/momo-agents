#!/usr/bin/env bash
# reset-stories.sh — rolls a pipeline run back to the post-BA state:
#   • Renames every state-encoded story file back to its bare STORY-NNN.md form
#   • Removes stories/HALT if present
#   • Clears all contents of workspace/ (preserving the directory itself)
#
# What is NOT touched: design/, .sentinels/, generated-test-applications/
#
# Usage: ./reset-stories.sh [--yes]
#   --yes   Skip the confirmation prompt (useful in scripts / CI)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STORIES_DIR="$SCRIPT_DIR/stories"
WORKSPACE_DIR="$SCRIPT_DIR/workspace"

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
AUTO_YES=false
for arg in "$@"; do
    [[ "$arg" == "--yes" ]] && AUTO_YES=true
done

# ---------------------------------------------------------------------------
# Confirmation banner
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Story Renamer — rename STORY-NNN.<complexity>.<state>.md → STORY-NNN.md
# ---------------------------------------------------------------------------
renamed_count=0

for f in "$STORIES_DIR"/STORY-*.*.*.md; do
    [[ -e "$f" ]] || continue
    # Extract just the filename
    name="$(basename "$f")"
    # Get the STORY-NNN prefix (everything before the first dot)
    prefix="${name%%.*}"
    bare_dest="$STORIES_DIR/${prefix}.md"
    mv "$f" "$bare_dest"
    renamed_count=$(( renamed_count + 1 ))
done

if [ "$renamed_count" -gt 0 ]; then
    echo "  ✓ stories/     renamed $renamed_count stor$([ "$renamed_count" -eq 1 ] && echo 'y' || echo 'ies') to bare form"
else
    echo "  – stories/     already clean (no state-encoded files found)"
fi

# ---------------------------------------------------------------------------
# HALT Cleaner — remove stories/HALT if present
# ---------------------------------------------------------------------------
if [ -f "$STORIES_DIR/HALT" ]; then
    rm -f "$STORIES_DIR/HALT"
    echo "  ✓ stories/HALT removed"
else
    echo "  – stories/HALT not present (nothing to remove)"
fi

# ---------------------------------------------------------------------------
# Workspace Cleaner — remove all contents of workspace/ (keep directory)
# ---------------------------------------------------------------------------
if [ -d "$WORKSPACE_DIR" ]; then
    find "$WORKSPACE_DIR" -mindepth 1 -delete 2>/dev/null || true
    echo "  ✓ workspace/   cleared"
else
    echo "  – workspace/   does not exist (nothing to clear)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║        Reset complete — ready to go  🧹         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Run './start-team.sh <feature-name>' to start a fresh session."
echo ""
