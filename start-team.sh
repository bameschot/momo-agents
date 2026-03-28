#!/usr/bin/env bash
# start-team.sh — opens ALL agents simultaneously, each in its own console window.
# Agents self-coordinate via the filesystem; no window needs to wait for another.
#
# Usage: ./start-team.sh <feature-name> [--junior-agents N] [--senior-agents N]
#        [--model-designer M] [--model-ba M] [--model-pi M]
#        [--model-junior M] [--model-senior M] [--model-reviewer M]
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
N_JUNIOR_AGENTS=2
N_SENIOR_AGENTS=1
DEFAULT_MODEL="claude-sonnet-4-6"
DEFAULT_JUNIOR_MODEL="claude-haiku-4-5-20251001"
DEFAULT_SENIOR_MODEL="claude-sonnet-4-6"
MODEL_DESIGNER="$DEFAULT_MODEL"
MODEL_BA="$DEFAULT_MODEL"
MODEL_PI="$DEFAULT_MODEL"
MODEL_JUNIOR="$DEFAULT_JUNIOR_MODEL"
MODEL_SENIOR="$DEFAULT_SENIOR_MODEL"
MODEL_REVIEWER="$DEFAULT_MODEL"

args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[$i]}" in
        --junior-agents=*)  N_JUNIOR_AGENTS="${args[$i]#*=}" ;;
        --junior-agents)    N_JUNIOR_AGENTS="${args[$((i + 1))]:-2}" ;;
        --senior-agents=*)  N_SENIOR_AGENTS="${args[$i]#*=}" ;;
        --senior-agents)    N_SENIOR_AGENTS="${args[$((i + 1))]:-1}" ;;
        --model-designer=*) MODEL_DESIGNER="${args[$i]#*=}" ;;
        --model-designer)   MODEL_DESIGNER="${args[$((i + 1))]:-$DEFAULT_MODEL}" ;;
        --model-ba=*)       MODEL_BA="${args[$i]#*=}" ;;
        --model-ba)         MODEL_BA="${args[$((i + 1))]:-$DEFAULT_MODEL}" ;;
        --model-pi=*)       MODEL_PI="${args[$i]#*=}" ;;
        --model-pi)         MODEL_PI="${args[$((i + 1))]:-$DEFAULT_MODEL}" ;;
        --model-junior=*)   MODEL_JUNIOR="${args[$i]#*=}" ;;
        --model-junior)     MODEL_JUNIOR="${args[$((i + 1))]:-$DEFAULT_JUNIOR_MODEL}" ;;
        --model-senior=*)   MODEL_SENIOR="${args[$i]#*=}" ;;
        --model-senior)     MODEL_SENIOR="${args[$((i + 1))]:-$DEFAULT_SENIOR_MODEL}" ;;
        --model-reviewer=*) MODEL_REVIEWER="${args[$i]#*=}" ;;
        --model-reviewer)   MODEL_REVIEWER="${args[$((i + 1))]:-$DEFAULT_MODEL}" ;;
    esac
done

if [ -z "$FEATURE" ]; then
    echo "Usage: $0 <feature-name> [options]"
    echo ""
    echo "  feature-name          Short kebab-case name for the feature to build"
    echo ""
    echo "  --junior-agents N     Junior Coding Agents to spawn — handle easy stories    (default: 2)"
    echo "  --senior-agents N     Senior Coding Agents to spawn — handle medium/hard     (default: 1)"
    echo "  --model-designer M    Model for Designer Agent      (default: $DEFAULT_MODEL)"
    echo "  --model-ba M          Model for Business Analyst    (default: $DEFAULT_MODEL)"
    echo "  --model-pi M          Model for Project Initialiser (default: $DEFAULT_MODEL)"
    echo "  --model-junior M      Model for Junior Coding Agents (default: $DEFAULT_JUNIOR_MODEL)"
    echo "  --model-senior M      Model for Senior Coding Agents (default: $DEFAULT_SENIOR_MODEL)"
    echo "  --model-reviewer M    Model for Story Reviewer      (default: $DEFAULT_MODEL)"
    exit 1
fi

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
DESIGN_DIR='$DESIGN_DIR'
WORKSPACE_DIR='$WORKSPACE_DIR'
SENTINEL_DIR='$SENTINEL_DIR'
PYTHON='$PYTHON'
ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY:-}'
MODEL_DESIGNER='$MODEL_DESIGNER'
MODEL_BA='$MODEL_BA'
MODEL_PI='$MODEL_PI'
MODEL_JUNIOR='$MODEL_JUNIOR'
MODEL_SENIOR='$MODEL_SENIOR'
MODEL_REVIEWER='$MODEL_REVIEWER'
CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────
WS_STATE="$(_workspace_initialized && echo "already initialised (PI will skip)" || echo "empty (PI will scaffold)")"

echo "╔══════════════════════════════════════════════════╗"
echo "║           momo-agents  ·  start-team             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Feature        : $FEATURE"
echo "  Junior Agents  : $N_JUNIOR_AGENTS  (easy stories — $MODEL_JUNIOR)"
echo "  Senior Agents  : $N_SENIOR_AGENTS  (medium + hard stories — $MODEL_SENIOR)"
echo "  Python         : $PYTHON"
echo "  Terminal       : $TERMINAL"
echo "  Workspace      : $WS_STATE"
echo ""
echo "  Models:"
echo "    Designer   : $MODEL_DESIGNER"
echo "    BA         : $MODEL_BA"
echo "    PI         : $MODEL_PI"
echo "    Junior     : $MODEL_JUNIOR"
echo "    Senior     : $MODEL_SENIOR"
echo "    Reviewer   : $MODEL_REVIEWER"
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
"$PYTHON" "${SCRIPT_DIR}/python-agents/designer.py" \
    --model "${MODEL_DESIGNER}" \
    --design-dir "${SCRIPT_DIR}/design"
touch "${SENTINEL_DIR}/designer.done"
echo ""
echo "[Designer Agent complete]"
WRAPPER

# ── Business Analyst ──────────────────────────────────────────────────────────
# Watches design/ for *.new.md files (written by the Designer Agent).
# Processes each one and renames it to *.processed.md when done.
# Re-triggers automatically if the Designer re-saves a design as *.new.md.
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
echo "Watching ${SCRIPT_DIR}/design/ for *.new.md files..."
echo ""

DESIGN_DIR="${SCRIPT_DIR}/design"

while true; do
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo "[Business Analyst] Pipeline complete — exiting."
        break
    fi

    shopt -s nullglob
    for design_file in "$DESIGN_DIR"/*.new.md; do
        [ -f "$design_file" ] || continue

        processed="${design_file%.new.md}.processed.md"
        feature="$(basename "${design_file%.new.md}")"

        echo "[Business Analyst] New design: ${feature} — decomposing into stories..."
        echo ""
        "$PYTHON" "${SCRIPT_DIR}/python-agents/business_analyst.py" \
            --design "$design_file" \
            --stories-dir "${STORIES_DIR}" \
            --model "${MODEL_BA}"

        # Mark as processed — overwrites any previous .processed.md for the same feature
        mv "$design_file" "$processed"
        touch "${SENTINEL_DIR}/ba.done"
        echo ""
        echo "[Business Analyst] ${feature} → processed. Resuming watch..."
        echo ""
    done
    shopt -u nullglob

    sleep 5
done
WRAPPER

# ── Project Initialiser ───────────────────────────────────────────────────────
# Skips when the workspace already has content.
# Otherwise watches design/ for the first *.new.md file the Designer produces,
# then scaffolds the workspace from that design — exactly once.
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
    exit 0
fi

echo "Waiting for a design/*.new.md file from the Designer..."

design_file=""
while true; do
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo "[Project Initialiser] Pipeline complete — exiting without scaffolding."
        exit 0
    fi

    shopt -s nullglob
    new_designs=("${DESIGN_DIR}"/*.new.md)
    shopt -u nullglob

    if [ "${#new_designs[@]}" -gt 0 ]; then
        design_file="${new_designs[0]}"
        break
    fi

    sleep 3
done

echo "Design file found: ${design_file}"
echo "Scaffolding workspace..."
echo ""
"$PYTHON" "${SCRIPT_DIR}/python-agents/project_initialiser.py" \
    --design "${design_file}" \
    --workspace-dir "${WORKSPACE_DIR}" \
    --model "${MODEL_PI}"
echo ""
echo "[Project Initialiser Agent complete]"
WRAPPER

# ── Junior Coding Agent (shared body, parameterised by $AGENT_ID) ────────────
# Claims easy stories only. Waits for PI to complete and for stories to exist.
# Loops through HALT/review cycles automatically — no new window needed.
cat > "$SENTINEL_DIR/junior_coding_agent_body.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"
# AGENT_ID is exported by the per-agent stub that execs this file.

printf "\033]0;Junior Coding Agent ${AGENT_ID} [easy]\007"
echo "╔══════════════════════════════════╗"
echo "║   Junior Coding Agent ${AGENT_ID} [easy]  ║"
echo "╚══════════════════════════════════╝"
echo "Handles: easy stories"
echo "Waiting for Project Initialiser to create workspace/CLAUDE.md..."

while [ ! -f "${WORKSPACE_DIR}/CLAUDE.md" ]; do sleep 3; done

echo "Waiting for stories..."
while [ "$(find "${STORIES_DIR}" -maxdepth 1 -name 'STORY-*.md' \
           2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]; do
    sleep 3
done

echo "Prerequisites ready — starting agent loop."
echo ""

while true; do
    "${PYTHON}" "${SCRIPT_DIR}/python-agents/junior_coding_agent.py" \
        --stories-dir "${STORIES_DIR}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_JUNIOR}"
    EXIT_CODE=$?

    # Orchestrator wrote pipeline_complete — clean exit
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo ""
        echo "[Junior Coding Agent ${AGENT_ID}] Pipeline complete — exiting."
        break
    fi

    # HALT — wait for reviewer to clear it, then resume
    if [ -f "${STORIES_DIR}/HALT" ]; then
        echo ""
        echo "[Junior Coding Agent ${AGENT_ID}] HALT detected — waiting for Story Reviewer..."
        while [ -f "${STORIES_DIR}/HALT" ]; do sleep 5; done
        sleep 2   # let renamed story files settle
        echo "[Junior Coding Agent ${AGENT_ID}] HALT cleared — resuming."
        echo ""
        continue
    fi

    # Unexpected non-zero exit — short pause before retrying
    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "[Junior Coding Agent ${AGENT_ID}] Agent exited with code $EXIT_CODE — retrying in 10s..."
        sleep 10
    fi
done

touch "${SENTINEL_DIR}/junior_${AGENT_ID}.done"
echo ""
echo "[Junior Coding Agent ${AGENT_ID} finished]"
WRAPPER

# Write a tiny per-agent stub for each junior agent.
# Unquoted heredoc (STUB) so $i and $SENTINEL_DIR expand at write time.
for i in $(seq 1 "$N_JUNIOR_AGENTS"); do
    cat > "$SENTINEL_DIR/run_junior_${i}.sh" << STUB
#!/usr/bin/env bash
export AGENT_ID=$i
exec bash '$SENTINEL_DIR/junior_coding_agent_body.sh'
STUB
done

# ── Senior Coding Agent (shared body, parameterised by $AGENT_ID) ────────────
# Claims medium and hard stories only. Waits for PI to complete and for stories.
# Loops through HALT/review cycles automatically — no new window needed.
cat > "$SENTINEL_DIR/senior_coding_agent_body.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"
# AGENT_ID is exported by the per-agent stub that execs this file.

printf "\033]0;Senior Coding Agent ${AGENT_ID} [medium/hard]\007"
echo "╔══════════════════════════════════════╗"
echo "║  Senior Coding Agent ${AGENT_ID} [medium/hard]  ║"
echo "╚══════════════════════════════════════╝"
echo "Handles: medium and hard stories"
echo "Waiting for Project Initialiser to create workspace/CLAUDE.md..."

while [ ! -f "${WORKSPACE_DIR}/CLAUDE.md" ]; do sleep 3; done

echo "Waiting for stories..."
while [ "$(find "${STORIES_DIR}" -maxdepth 1 -name 'STORY-*.md' \
           2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]; do
    sleep 3
done

echo "Prerequisites ready — starting agent loop."
echo ""

while true; do
    "${PYTHON}" "${SCRIPT_DIR}/python-agents/senior_coding_agent.py" \
        --stories-dir "${STORIES_DIR}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_SENIOR}"
    EXIT_CODE=$?

    # Orchestrator wrote pipeline_complete — clean exit
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo ""
        echo "[Senior Coding Agent ${AGENT_ID}] Pipeline complete — exiting."
        break
    fi

    # HALT — wait for reviewer to clear it, then resume
    if [ -f "${STORIES_DIR}/HALT" ]; then
        echo ""
        echo "[Senior Coding Agent ${AGENT_ID}] HALT detected — waiting for Story Reviewer..."
        while [ -f "${STORIES_DIR}/HALT" ]; do sleep 5; done
        sleep 2   # let renamed story files settle
        echo "[Senior Coding Agent ${AGENT_ID}] HALT cleared — resuming."
        echo ""
        continue
    fi

    # Unexpected non-zero exit — short pause before retrying
    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "[Senior Coding Agent ${AGENT_ID}] Agent exited with code $EXIT_CODE — retrying in 10s..."
        sleep 10
    fi
done

touch "${SENTINEL_DIR}/senior_${AGENT_ID}.done"
echo ""
echo "[Senior Coding Agent ${AGENT_ID} finished]"
WRAPPER

# Write a tiny per-agent stub for each senior agent.
for i in $(seq 1 "$N_SENIOR_AGENTS"); do
    cat > "$SENTINEL_DIR/run_senior_${i}.sh" << STUB
#!/usr/bin/env bash
export AGENT_ID=$i
exec bash '$SENTINEL_DIR/senior_coding_agent_body.sh'
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
    "${PYTHON}" "${SCRIPT_DIR}/python-agents/story_reviewer.py" \
        --stories-dir "${STORIES_DIR}" \
        --model "${MODEL_REVIEWER}"
    echo ""
    echo "[Story Reviewer] Session complete — resuming watch."
    echo ""
done
WRAPPER

chmod +x \
    "$SENTINEL_DIR/run_designer.sh" \
    "$SENTINEL_DIR/run_ba.sh" \
    "$SENTINEL_DIR/run_pi.sh" \
    "$SENTINEL_DIR/junior_coding_agent_body.sh" \
    "$SENTINEL_DIR/senior_coding_agent_body.sh" \
    "$SENTINEL_DIR/run_watchdog.sh" \
    "$SENTINEL_DIR/run_story_reviewer.sh"

for i in $(seq 1 "$N_JUNIOR_AGENTS"); do
    chmod +x "$SENTINEL_DIR/run_junior_${i}.sh"
done

for i in $(seq 1 "$N_SENIOR_AGENTS"); do
    chmod +x "$SENTINEL_DIR/run_senior_${i}.sh"
done

# ─────────────────────────────────────────────────────────────────────────────
# Launch ALL windows simultaneously
# ─────────────────────────────────────────────────────────────────────────────
TOTAL=$(( N_JUNIOR_AGENTS + N_SENIOR_AGENTS + 5 ))
echo "Opening $TOTAL windows simultaneously ($N_JUNIOR_AGENTS junior + $N_SENIOR_AGENTS senior + 5 fixed agents)..."
echo ""

open_window "🎨 Designer Agent"        "$SENTINEL_DIR/run_designer.sh"
open_window "📋 Business Analyst"      "$SENTINEL_DIR/run_ba.sh"
open_window "🏗️  Project Initialiser"  "$SENTINEL_DIR/run_pi.sh"
open_window "🐕 Watchdog"              "$SENTINEL_DIR/run_watchdog.sh"
open_window "🔍 Story Reviewer"        "$SENTINEL_DIR/run_story_reviewer.sh"

for i in $(seq 1 "$N_JUNIOR_AGENTS"); do
    open_window "🟢 Junior Coding Agent $i [easy]"        "$SENTINEL_DIR/run_junior_${i}.sh"
done

for i in $(seq 1 "$N_SENIOR_AGENTS"); do
    open_window "🔵 Senior Coding Agent $i [medium/hard]" "$SENTINEL_DIR/run_senior_${i}.sh"
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
