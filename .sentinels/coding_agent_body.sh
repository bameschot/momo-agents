#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"
# AGENT_ID is exported by the per-agent stub that execs this file.

echo "╔══════════════════════════════════╗"
echo "║       Coding Agent ${AGENT_ID}              ║"
echo "╚══════════════════════════════════╝"
echo "Waiting for Project Initialiser..."

while [ ! -f "${SENTINEL_DIR}/pi.done" ]; do sleep 3; done

echo "Waiting for stories..."
while [ "$(find "${STORIES_DIR}" -maxdepth 1 -name 'STORY-*.md' \
           2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]; do
    sleep 3
done

echo "Prerequisites ready — starting agent loop."
echo ""

while true; do
    "${PYTHON}" "${SCRIPT_DIR}/python-agents/coding_agent.py"

    if [ ! -f "${STORIES_DIR}/HALT" ]; then
        echo ""
        echo "[Coding Agent ${AGENT_ID}] No more stories to claim — done."
        break
    fi

    echo ""
    echo "[Coding Agent ${AGENT_ID}] HALT detected — waiting for Story Reviewer..."
    while [ -f "${STORIES_DIR}/HALT" ]; do sleep 5; done
    sleep 2   # let renamed story files settle
    echo "[Coding Agent ${AGENT_ID}] HALT cleared — resuming."
    echo ""
done

touch "${SENTINEL_DIR}/coding_${AGENT_ID}.done"
echo ""
echo "[Coding Agent ${AGENT_ID} finished]"
