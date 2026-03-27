#!/usr/bin/env bash
source "$(dirname "$0")/config.sh"

echo "╔══════════════════════════════════╗"
echo "║            Watchdog              ║"
echo "╚══════════════════════════════════╝"
exec bash "${SCRIPT_DIR}/watchdog.sh"
