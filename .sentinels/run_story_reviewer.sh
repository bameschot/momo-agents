#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║       Story Reviewer Agent       ║"
echo "╚══════════════════════════════════╝"
echo "Watching for HALT file..."
echo ""

while true; do
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo "[Story Reviewer] Pipeline complete — exiting."
        break
    fi

    if [ ! -f "${STORIES_DIR}/HALT" ]; then
        sleep 5
        continue
    fi

    echo "[Story Reviewer] HALT detected — starting review session..."
    echo ""
    "${PYTHON}" "${SCRIPT_DIR}/python-agents/story_reviewer.py"
    echo ""
    echo "[Story Reviewer] Session complete — resuming watch."
    echo ""
done
