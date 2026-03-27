#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║    Project Initialiser Agent     ║"
echo "╚══════════════════════════════════╝"

ws_content=$(find "${WORKSPACE_DIR}" -mindepth 1 -maxdepth 1 \
    ! -name "CLAUDE.md" 2>/dev/null | wc -l | tr -d ' ')

if [ "${ws_content}" -gt 0 ]; then
    echo "Workspace already initialised — skipping scaffold step."
    touch "${SENTINEL_DIR}/pi.done"
    exit 0
fi

echo "Waiting for design file: ${DESIGN_FILE}"
while [ ! -f "${DESIGN_FILE}" ]; do sleep 3; done
echo "Design file found — scaffolding workspace..."
echo ""
"$PYTHON" "${SCRIPT_DIR}/python-agents/project_initialiser.py" --design "${DESIGN_FILE}"
touch "${SENTINEL_DIR}/pi.done"
echo ""
echo "[Project Initialiser Agent complete]"
