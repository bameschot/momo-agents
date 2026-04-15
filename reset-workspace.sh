#!/usr/bin/env bash
# reset-workspace.sh — resets a workspace back to a pre-implementation state.
#
# What this does:
#   • Renames design/*.processed.md → *.new.md  (marks designs as unprocessed)
#   • Renames all story files → bare STORY-NNN.md  (strips state and complexity)
#   • Removes everything else in the workspace except stories/ and design/
#     (including .git, .sentinels, src/, tests/, CLAUDE.md, etc.)
#
# Usage: ./reset-workspace.sh --workspace <path> [--yes]
#   --workspace <path>   Path to the workspace directory (required)
#   --yes                Skip the confirmation prompt

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─────────────────────────────────────────────────────────────────────────────
# Argument Parsing
# ─────────────────────────────────────────────────────────────────────────────
AUTO_YES=false
WORKSPACE_DIR=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --workspace)
            WORKSPACE_DIR="$2"
            shift 2
            ;;
        --yes)
            AUTO_YES=true
            shift
            ;;
        *)
            echo "  Unknown argument: $1"
            echo "  Usage: ./reset-workspace.sh --workspace <path> [--yes]"
            exit 1
            ;;
    esac
done

if [[ -z "$WORKSPACE_DIR" ]]; then
    echo "  Error: --workspace <path> is required."
    echo "  Usage: ./reset-workspace.sh --workspace <path> [--yes]"
    exit 1
fi

# Resolve to absolute path
WORKSPACE_DIR="$(cd "$WORKSPACE_DIR" && pwd)"
DESIGN_DIR="$WORKSPACE_DIR/design"
STORIES_DIR="$WORKSPACE_DIR/stories"

if [[ ! -d "$WORKSPACE_DIR" ]]; then
    echo "  Error: workspace directory does not exist: $WORKSPACE_DIR"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Confirmation Banner
# ─────────────────────────────────────────────────────────────────────────────
echo "╔══════════════════════════════════════════════════╗"
echo "║       momo-agents  ·  reset-workspace            ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Workspace: $WORKSPACE_DIR"
echo ""
echo "  This will:"
echo "    • Rename design/*.processed.md  →  *.new.md"
echo "    • Rename all story files        →  bare STORY-NNN.md"
echo "    • Remove everything else in the workspace"
echo "      (including .git, .sentinels, src/, tests/, CLAUDE.md, ...)"
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
# Design Reset — rename *.processed.md → *.new.md
# ─────────────────────────────────────────────────────────────────────────────
design_count=0
if [[ -d "$DESIGN_DIR" ]]; then
    for f in "$DESIGN_DIR"/*.processed.md; do
        [[ -e "$f" ]] || continue
        filename="$(basename "$f")"
        bare="${filename%.processed.md}"
        mv "$f" "$DESIGN_DIR/${bare}.new.md"
        design_count=$(( design_count + 1 ))
    done
fi

if [[ "$design_count" -gt 0 ]]; then
    echo "  ✓ renamed $design_count design(s) to .new.md"
else
    echo "  – design/      nothing to rename"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Story Reset — rename all STORY-NNN.* variants back to STORY-NNN.md
# ─────────────────────────────────────────────────────────────────────────────
story_count=0
if [[ -d "$STORIES_DIR" ]]; then
    # Match any STORY-NNN file that has more than one dot segment (i.e. not bare)
    for f in "$STORIES_DIR"/STORY-[0-9]*.*.md; do
        [[ -e "$f" ]] || continue
        filename="$(basename "$f")"
        # Extract just the STORY-NNN prefix (everything before the first dot after the number)
        prefix="${filename%%.*}"
        bare_name="${prefix}.md"
        target="$STORIES_DIR/$bare_name"
        # Skip if it somehow already is the bare name
        [[ "$f" == "$target" ]] && continue
        mv "$f" "$target"
        story_count=$(( story_count + 1 ))
    done
fi

if [[ "$story_count" -gt 0 ]]; then
    echo "  ✓ renamed $story_count story file(s) to bare STORY-NNN.md"
else
    echo "  – stories/     nothing to rename"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Workspace Cleaner — remove everything except stories/ and design/
# ─────────────────────────────────────────────────────────────────────────────
removed_count=0
while IFS= read -r -d '' entry; do
    rm -rf "$entry"
    removed_count=$(( removed_count + 1 ))
done < <(find "$WORKSPACE_DIR" -mindepth 1 -maxdepth 1 \
    ! -name "stories" ! -name "design" \
    -print0)

if [[ "$removed_count" -gt 0 ]]; then
    echo "  ✓ removed $removed_count item(s) from workspace (src/, tests/, .git, .sentinels, ...)"
else
    echo "  – workspace/   nothing else to remove"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Done
# ─────────────────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║      Reset complete — workspace is clean         ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Run './start-team.sh --workspace $WORKSPACE_DIR' to start a fresh run."
echo ""
