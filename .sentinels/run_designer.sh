#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║        Designer Agent            ║"
echo "╚══════════════════════════════════╝"
echo "Ask clarifying questions then type 'write' to produce the design file."
echo ""
"$PYTHON" "${SCRIPT_DIR}/python-agents/designer.py"
touch "${SENTINEL_DIR}/designer.done"
echo ""
echo "[Designer Agent complete]"
