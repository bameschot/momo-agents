#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║      Business Analyst Agent      ║"
echo "╚══════════════════════════════════╝"
echo "Waiting for design file: ${DESIGN_FILE}"
while [ ! -f "${DESIGN_FILE}" ]; do sleep 3; done
echo "Design file found — decomposing into stories..."
echo ""
"$PYTHON" "${SCRIPT_DIR}/python-agents/business_analyst.py" --design "${DESIGN_FILE}"
touch "${SENTINEL_DIR}/ba.done"
echo ""
echo "[Business Analyst Agent complete]"
