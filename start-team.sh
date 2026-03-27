#!/usr/bin/env bash
# start-team.sh — opens ALL agents simultaneously, each in its own console window.
# Agents self-coordinate via the filesystem; no window needs to wait for another.
#
# Usage: ./start-team.sh <feature-name> [--dev-agents N]
#
# Supported terminal environments (auto-detected in priority order):
#   macOS   : Terminal.app via osascript
#   Linux   : gnome-terminal · konsole · xfce4-terminal · mate-terminal · xterm
#   Fallback: tmux (new session "momo-agents"; attach with: tmux attach -t momo-agents)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Arguments
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
STORIES_DIR="$SCRIPT_DIR/stories"
DESIGN_DIR="$SCRIPT_DIR/design"
WORKSPACE_DIR="$SCRIPT_DIR/workspace"
SENTINEL_DIR="$SCRIPT_DIR/.sentinels"

FEATURE="${1:-}"
N_DEV_AGENTS=2

args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[$i]}" in
        --dev-agents=*) N_DEV_AGENTS="${args[$i]#*=}" ;;
        --dev-agents)   N_DEV_AGENTS="${args[$((i + 1))]:-2}" ;;
    esac
done

if [ -z "$FEATURE" ]; then
    echo "Usage: $0 <feature-name> [--dev-agents N]"
    echo ""
    echo "  feature-name   Short kebab-case name for the feature to build"
    echo "  --dev-agents N Number of parallel Coding Agents to spawn (default: 2)"
    echo "                 All other agents (Designer, BA, PI, Watchdog, Reviewer)"
    echo "                 always start as a single instance."
    exit 1
fi

DESIGN_FILE="$DESIGN_DIR/${FEATURE}.md"

# ─────────────────────────────────────────────────────────────────────────────
# Python — prefer .venv, fall back to system python3 / python
# ─────────────────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

# ─────────────────────────────────────────────────────────────────────────────
# Environment — load .env if present
# ─────────────────────────────────────────────────────────────────────────────
if [ -f "$SCRIPT_DIR/.env" ]; then
    # shellcheck disable=SC1091
    set -a; source "$SCRIPT_DIR/.env"; set +a
fi

# ─────────────────────────────────────────────────────────────────────────────
# Terminal detection
# ─────────────────────────────────────────────────────────────────────────────
_detect_terminal() {
    if [[ "$OSTYPE" == "darwin"* ]];         then echo "macos"
    elif command -v gnome-terminal &>/dev/null; then echo "gnome-terminal"
    elif command -v konsole        &>/dev/null; then echo "konsole"
    elif command -v xfce4-terminal &>/dev/null; then echo "xfce4-terminal"
    elif command -v mate-terminal  &>/dev/null; then echo "mate-terminal"
    elif command -v xterm          &>/dev/null; then echo "xterm"
    elif command -v tmux           &>/dev/null; then echo "tmux"
    else echo "none"
    fi
}

TERMINAL="$(_detect_terminal)"
TMUX_SESSION="momo-agents"
_TMUX_FIRST_WINDOW=true

# ─────────────────────────────────────────────────────────────────────────────
# open_window <title> <wrapper-script>
#   Opens a new terminal window and runs the given wrapper script inside it.
#   Returns immediately — does not wait for the script to finish.
# ─────────────────────────────────────────────────────────────────────────────
open_window() {
    local title="$1"
    local script="$2"

    case "$TERMINAL" in
        macos)
            osascript <<APPLESCRIPT
tell application "Terminal"
    set t to do script "bash '$script'"
    delay 0.2
    set custom title of t to "$title"
    activate
end tell
APPLESCRIPT
            ;;

        gnome-terminal)
            gnome-terminal --title="$title" \
                -- bash -c "bash '$script'; echo ''; echo '[done — press enter to close]'; read -r" &
            ;;

        konsole)
            konsole --new-tab -p "tabtitle=$title" \
                -e bash -c "bash '$script'; read -r" &
            ;;

        xfce4-terminal)
            xfce4-terminal --title="$title" \
                -e "bash -c \"bash '$script'; read -r\"" &
            ;;

        mate-terminal)
            mate-terminal --title="$title" \
                -e "bash -c \"bash '$script'; read -r\"" &
            ;;

        xterm)
            xterm -title "$title" -e "bash '$script'" &
            ;;

        tmux)
            if [ "$_TMUX_FIRST_WINDOW" = "true" ]; then
                tmux new-session -d -s "$TMUX_SESSION" -n "$title" \
                    "bash '$script'" 2>/dev/null || true
                _TMUX_FIRST_WINDOW=false
            else
                tmux new-window -t "$TMUX_SESSION" -n "$title" "bash '$script'"
            fi
            ;;

        none)
            local log="$SENTINEL_DIR/${title// /_}.log"
            bash "$script" >"$log" 2>&1 &
            echo "  [no terminal] logging → $log"
            ;;
    esac
}

# ─────────────────────────────────────────────────────────────────────────────
# Workspace initialisation probe
# ─────────────────────────────────────────────────────────────────────────────
_workspace_initialized() {
    # True when workspace contains anything beyond the skeleton CLAUDE.md
    local n
    n=$(find "$WORKSPACE_DIR" -mindepth 1 -maxdepth 1 \
            ! -name "CLAUDE.md" 2>/dev/null | wc -l | tr -d ' ')
    [ "$n" -gt 0 ]
}

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p "$SENTINEL_DIR"
rm -f "$SENTINEL_DIR"/*.done "$SENTINEL_DIR/pipeline_complete" 2>/dev/null || true

# ─────────────────────────────────────────────────────────────────────────────
# Write shared config — sourced by every wrapper script at runtime
# ─────────────────────────────────────────────────────────────────────────────
# NOTE: unquoted heredoc — variables expand NOW so paths are baked in.
cat > "$SENTINEL_DIR/config.sh" << CONFIG
# Auto-generated by start-team.sh — do not edit
SCRIPT_DIR='$SCRIPT_DIR'
STORIES_DIR='$STORIES_DIR'
WORKSPACE_DIR='$WORKSPACE_DIR'
DESIGN_FILE='$DESIGN_FILE'
SENTINEL_DIR='$SENTINEL_DIR'
PYTHON='$PYTHON'
ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY:-}'
CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────
WS_STATE="$(_workspace_initialized && echo "already initialised (PI will skip)" || echo "empty (PI will scaffold)")"

echo "╔══════════════════════════════════════════════════╗"
echo "║           momo-agents  ·  start-team             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Feature    : $FEATURE"
echo "  Dev Agents : $N_DEV_AGENTS  (coding agents only; all others are single-instance)"
echo "  Python     : $PYTHON"
echo "  Terminal   : $TERMINAL"
echo "  Workspace  : $WS_STATE"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Write wrapper scripts
# All heredocs below use << 'WRAPPER' (quoted) so the script body is written
# verbatim — variables resolve at *runtime* when the wrapper is executed.
# ─────────────────────────────────────────────────────────────────────────────

# ── Designer ─────────────────────────────────────────────────────────────────
cat > "$SENTINEL_DIR/run_designer.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Designer Agent\007'
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
WRAPPER

# ── Business Analyst ──────────────────────────────────────────────────────────
# Watches the design/ folder continuously. Triggers (or re-triggers) whenever
# any .md file is created or its modification time changes.
cat > "$SENTINEL_DIR/run_ba.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Business Analyst\007'
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
WRAPPER

# ── Project Initialiser ───────────────────────────────────────────────────────
# Skips automatically when the workspace already has content.
# Otherwise waits for the design file, then scaffolds.
cat > "$SENTINEL_DIR/run_pi.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Project Initialiser\007'
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
WRAPPER

# ── Coding Agent (shared body, parameterised by $AGENT_ID) ───────────────────
# Waits for PI to complete (or be skipped) and for at least one story to appear.
# Loops through HALT/review cycles automatically — no new window needed.
cat > "$SENTINEL_DIR/coding_agent_body.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"
# AGENT_ID is exported by the per-agent stub that execs this file.

printf "\033]0;Coding Agent ${AGENT_ID}\007"
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
    EXIT_CODE=$?

    # Orchestrator wrote pipeline_complete — clean exit
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo ""
        echo "[Coding Agent ${AGENT_ID}] Pipeline complete — exiting."
        break
    fi

    # HALT — wait for reviewer to clear it, then resume
    if [ -f "${STORIES_DIR}/HALT" ]; then
        echo ""
        echo "[Coding Agent ${AGENT_ID}] HALT detected — waiting for Story Reviewer..."
        while [ -f "${STORIES_DIR}/HALT" ]; do sleep 5; done
        sleep 2   # let renamed story files settle
        echo "[Coding Agent ${AGENT_ID}] HALT cleared — resuming."
        echo ""
        continue
    fi

    # Unexpected non-zero exit — short pause before retrying
    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "[Coding Agent ${AGENT_ID}] Agent exited with code $EXIT_CODE — retrying in 10s..."
        sleep 10
    fi
done

touch "${SENTINEL_DIR}/coding_${AGENT_ID}.done"
echo ""
echo "[Coding Agent ${AGENT_ID} finished]"
WRAPPER

# Write a tiny per-agent stub that sets AGENT_ID and execs the shared body.
# Unquoted heredoc (STUB) so $i and $SENTINEL_DIR expand at write time.
for i in $(seq 1 "$N_DEV_AGENTS"); do
    cat > "$SENTINEL_DIR/run_coding_${i}.sh" << STUB
#!/usr/bin/env bash
export AGENT_ID=$i
exec bash '$SENTINEL_DIR/coding_agent_body.sh'
STUB
done

# ── Watchdog ──────────────────────────────────────────────────────────────────
cat > "$SENTINEL_DIR/run_watchdog.sh" << 'WRAPPER'
#!/usr/bin/env bash
printf '\033]0;Watchdog\007'
source "$(dirname "$0")/config.sh"

echo "╔══════════════════════════════════╗"
echo "║            Watchdog              ║"
echo "╚══════════════════════════════════╝"
exec bash "${SCRIPT_DIR}/watchdog.sh"
WRAPPER

# ── Story Reviewer ────────────────────────────────────────────────────────────
# Runs continuously — wakes on HALT, reviews with user, then waits again.
# Exits cleanly when the orchestrator writes the pipeline_complete sentinel.
cat > "$SENTINEL_DIR/run_story_reviewer.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Story Reviewer\007'
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
WRAPPER

chmod +x \
    "$SENTINEL_DIR/run_designer.sh" \
    "$SENTINEL_DIR/run_ba.sh" \
    "$SENTINEL_DIR/run_pi.sh" \
    "$SENTINEL_DIR/coding_agent_body.sh" \
    "$SENTINEL_DIR/run_watchdog.sh" \
    "$SENTINEL_DIR/run_story_reviewer.sh"

for i in $(seq 1 "$N_DEV_AGENTS"); do
    chmod +x "$SENTINEL_DIR/run_coding_${i}.sh"
done

# ─────────────────────────────────────────────────────────────────────────────
# Launch ALL windows simultaneously
# ─────────────────────────────────────────────────────────────────────────────
TOTAL=$(( N_DEV_AGENTS + 5 ))   # 5 fixed: designer + ba + pi + watchdog + reviewer; plus N_DEV_AGENTS coding agents
echo "Opening $TOTAL windows simultaneously ($N_DEV_AGENTS coding agent(s) + 5 fixed agents)..."
echo ""

open_window "🎨 Designer Agent"        "$SENTINEL_DIR/run_designer.sh"
open_window "📋 Business Analyst"      "$SENTINEL_DIR/run_ba.sh"
open_window "🏗️  Project Initialiser"  "$SENTINEL_DIR/run_pi.sh"
open_window "🐕 Watchdog"              "$SENTINEL_DIR/run_watchdog.sh"
open_window "🔍 Story Reviewer"        "$SENTINEL_DIR/run_story_reviewer.sh"

for i in $(seq 1 "$N_DEV_AGENTS"); do
    open_window "💻 Coding Agent $i"   "$SENTINEL_DIR/run_coding_${i}.sh"
done

if [ "$TERMINAL" = "tmux" ]; then
    echo ""
    echo "  All windows are in tmux session '$TMUX_SESSION'."
    echo "  To watch the team work, run:"
    echo "    tmux attach -t $TMUX_SESSION"
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# Monitor — print status on change; runs until Ctrl+C
# Coding agents poll indefinitely so the pipeline is open-ended: the BA may
# write new stories at any time (e.g. after a design update) and agents will
# pick them up automatically. Press Ctrl+C in this terminal to shut everything
# down gracefully.
# ─────────────────────────────────────────────────────────────────────────────
echo "Monitoring pipeline (press Ctrl+C to shut down the team)..."
echo ""

_count_pending_stories() {
    local count=0 f base
    for f in "$STORIES_DIR"/STORY-*.md; do
        [[ -f "$f" ]] || continue
        base="$(basename "$f")"
        [[ "$base" =~ ^STORY-[0-9]+\.md$ ]] && (( count++ )) || true
    done
    echo "$count"
}

_teardown() {
    echo ""
    echo "Shutting down team..."
    touch "$SENTINEL_DIR/pipeline_complete"   # signals all agents to exit
    pkill -f "watchdog.sh" 2>/dev/null || true
    sleep 2
    rm -rf "$SENTINEL_DIR"
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║               Team shut down  👋                ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    bash "$SCRIPT_DIR/status.sh"
    exit 0
}

trap '_teardown' INT TERM

LAST_STATUS=""
while true; do
    pending="$(_count_pending_stories)"
    working=$(find "$STORIES_DIR" -maxdepth 1 -name "STORY-*.working.md"  2>/dev/null | wc -l | tr -d ' ')
    done_n=$(find  "$STORIES_DIR" -maxdepth 1 -name "STORY-*.done.md"     2>/dev/null | wc -l | tr -d ' ')
    failed=$(find  "$STORIES_DIR" -maxdepth 1 -name "STORY-*.failed.md"   2>/dev/null | wc -l | tr -d ' ')
    halt_flag=$( [ -f "$STORIES_DIR/HALT" ] && echo "  ⚠ HALTED" || echo "" )

    STATUS="pending=${pending}  working=${working}  done=${done_n}  failed=${failed}${halt_flag}"
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        echo "  $(date '+%H:%M:%S')  $STATUS"
        LAST_STATUS="$STATUS"
    fi

    sleep 10
done
