#!/usr/bin/env bash
# Orchestrates the full momo-agents pipeline.
# Usage: ./orchestrate.sh <feature-name> [--agents N]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STORIES_DIR="$SCRIPT_DIR/stories"
DESIGN_DIR="$SCRIPT_DIR/design"
ROLES_DIR="$SCRIPT_DIR/roles"

FEATURE="${1:-}"
N_AGENTS="${2:-3}"

if [ -z "$FEATURE" ]; then
    echo "Usage: $0 <feature-name> [--agents N]"
    exit 1
fi

# Parse --agents flag
for i in "$@"; do
    case $i in
        --agents=*) N_AGENTS="${i#*=}" ;;
        --agents)   shift; N_AGENTS="$1" ;;
    esac
done

DESIGN_FILE="$DESIGN_DIR/${FEATURE}.md"

echo "=== momo-agents orchestrator ==="
echo "Feature : $FEATURE"
echo "Agents  : $N_AGENTS"
echo ""

# Step 1: Designer Agent (interactive)
echo "[1/7] Launching Designer Agent..."
claude --system-prompt "$ROLES_DIR/designer.md" --print "Design the feature: $FEATURE"
# Designer saves to design/<feature>.md on `write` command

if [ ! -f "$DESIGN_FILE" ]; then
    echo "Error: design file not found at $DESIGN_FILE — did the Designer Agent write it?"
    exit 1
fi

# Step 2: Business Analyst Agent
echo "[2/7] Launching Business Analyst Agent..."
claude --system-prompt "$ROLES_DIR/business-analyst.md" --print "Break down the design at $DESIGN_FILE into stories in $STORIES_DIR"

# Step 3: Project Initialiser Agent
echo "[3/7] Launching Project Initialiser Agent..."
claude --system-prompt "$ROLES_DIR/project-initialiser.md" --print "Initialise the workspace from the design at $DESIGN_FILE"

# Pipeline loop: spawn agents, handle HALT, repeat until done
while true; do
    # Step 4: Start watchdog in background
    echo "[4/7] Starting watchdog..."
    bash "$SCRIPT_DIR/watchdog.sh" &
    WATCHDOG_PID=$!

    # Step 5: Spawn N Coding Agents in parallel
    echo "[5/7] Spawning $N_AGENTS Coding Agent(s)..."
    AGENT_PIDS=()
    for i in $(seq 1 "$N_AGENTS"); do
        claude --system-prompt "$ROLES_DIR/coding-agent.md" \
            --print "Claim and implement the next available story in $STORIES_DIR. Workspace is at $SCRIPT_DIR/workspace." &
        AGENT_PIDS+=($!)
    done

    # Wait for all Coding Agents to exit
    for pid in "${AGENT_PIDS[@]}"; do
        wait "$pid" || true
    done

    # Step 6: Stop watchdog
    echo "[6/7] Stopping watchdog..."
    kill "$WATCHDOG_PID" 2>/dev/null || true
    wait "$WATCHDOG_PID" 2>/dev/null || true

    # Step 7: Check for HALT
    if [ -f "$STORIES_DIR/HALT" ]; then
        echo "[7/7] HALT detected — launching Story Reviewer..."
        claude --system-prompt "$ROLES_DIR/story-reviewer.md" \
            --print "Review failed stories in $STORIES_DIR and work with the user to resolve them."
        # Story Reviewer deletes HALT when done; loop back to step 4
    else
        echo "[7/7] No HALT file — all stories complete."
        break
    fi
done

echo ""
echo "=== Pipeline complete ==="
bash "$SCRIPT_DIR/status.sh"
