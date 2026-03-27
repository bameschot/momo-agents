#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║      Business Analyst Agent      ║"
echo "╚══════════════════════════════════╝"
echo "Watching ${SCRIPT_DIR}/design/ for .md changes..."
echo ""

DESIGN_DIR="${SCRIPT_DIR}/design"
MTIME_STORE="${SENTINEL_DIR}/ba_mtimes"
mkdir -p "$MTIME_STORE"

# Cross-platform mtime (macOS stat -f, Linux stat -c)
_mtime() {
    stat -f "%m" "$1" 2>/dev/null || stat -c "%Y" "$1" 2>/dev/null || echo "0"
}

# Derive a safe filename from the design file path for mtime tracking
_mtime_key() {
    basename "$1" | sed 's/[^a-zA-Z0-9._-]/_/g'
}

while true; do
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo "[Business Analyst] Pipeline complete — exiting."
        break
    fi

    shopt -s nullglob
    for design_file in "$DESIGN_DIR"/*.md; do
        [ -f "$design_file" ] || continue

        key="$(_mtime_key "$design_file")"
        mtime_file="$MTIME_STORE/$key"
        current_mtime="$(_mtime "$design_file")"
        last_mtime="$(cat "$mtime_file" 2>/dev/null || echo "")"

        if [ "$current_mtime" != "$last_mtime" ]; then
            # Record new mtime immediately to avoid double-triggering
            echo "$current_mtime" > "$mtime_file"
            echo "[Business Analyst] Detected change: $(basename "$design_file") — decomposing into stories..."
            echo ""
            "$PYTHON" "${SCRIPT_DIR}/python-agents/business_analyst.py" --design "$design_file"
            touch "${SENTINEL_DIR}/ba.done"
            echo ""
            echo "[Business Analyst] Stories updated for $(basename "$design_file"). Resuming watch..."
            echo ""
        fi
    done
    shopt -u nullglob

    sleep 5
done
