#!/usr/bin/env bash
# start-team.sh — opens ALL agents simultaneously, each in its own console window.
# Agents self-coordinate via the filesystem; no window needs to wait for another.
#
# Usage: ./start-team.sh <feature-name> [options]
#        Options: [--junior-agents N] [--senior-agents N]
#                 [--model-designer M] [--model-ba M] [--model-pi M]
#                 [--model-junior M] [--model-senior M] [--model-reviewer M]
#
# Supported terminal environments (auto-detected in priority order):
#   macOS   : Terminal.app via osascript
#   Linux   : gnome-terminal · konsole · xfce4-terminal · mate-terminal · xterm
#   Fallback: tmux (new session "momo-agents"; attach with: tmux attach -t momo-agents)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Paths
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$SCRIPT_DIR/workspace"
DESIGN_DIR="$WORKSPACE_DIR/design"
STORIES_DIR="$WORKSPACE_DIR/stories"
SENTINEL_DIR="$WORKSPACE_DIR/.sentinels"

# ─────────────────────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────────────────────
FEATURE="${1:-}"
N_JUNIOR_AGENTS=2
N_SENIOR_AGENTS=1

DEFAULT_MODEL="claude-sonnet-4-6"
DEFAULT_JUNIOR_MODEL="claude-haiku-4-5-20251001"
DEFAULT_SENIOR_MODEL="claude-sonnet-4-6"
DEFAULT_PI_MODEL="claude-haiku-4-5-20251001"

MODEL_DESIGNER="$DEFAULT_MODEL"
MODEL_BA="$DEFAULT_MODEL"
MODEL_PI="$DEFAULT_PI_MODEL"
MODEL_JUNIOR="$DEFAULT_JUNIOR_MODEL"
MODEL_SENIOR="$DEFAULT_SENIOR_MODEL"
MODEL_REVIEWER="$DEFAULT_MODEL"

# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────
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
        --model-pi)         MODEL_PI="${args[$((i + 1))]:-$DEFAULT_PI_MODEL}" ;;
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
    echo "  --model-pi M          Model for Project Initialiser (default: $DEFAULT_PI_MODEL)"
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
    if [[ "$OSTYPE" == "darwin"* ]];           then echo "macos"
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
#   Opens a new terminal window/tab running the given wrapper script.
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
            # No terminal available — run in background and log to file
            local log="$SENTINEL_DIR/${title// /_}.log"
            bash "$script" >"$log" 2>&1 &
            echo "  [no terminal] logging → $log"
            ;;
    esac
}

# ─────────────────────────────────────────────────────────────────────────────
# _workspace_initialized — true when workspace/CLAUDE.md exists
# ─────────────────────────────────────────────────────────────────────────────
_workspace_initialized() {
    [ -f "$WORKSPACE_DIR/CLAUDE.md" ]
}

# ─────────────────────────────────────────────────────────────────────────────
# Setup — create sentinel directory; clear any stale pipeline_complete sentinel
# ─────────────────────────────────────────────────────────────────────────────
mkdir -p "$SENTINEL_DIR" "$SENTINEL_DIR/tokens"
rm -f "$SENTINEL_DIR/pipeline_complete" 2>/dev/null || true
touch "$SENTINEL_DIR/run-log.jsonl"

# ─────────────────────────────────────────────────────────────────────────────
# Write shared config — sourced by every wrapper script at runtime.
# Unquoted heredoc: variables expand NOW so all paths are baked in at write time.
# ─────────────────────────────────────────────────────────────────────────────
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
RUN_LOG='$SENTINEL_DIR/run-log.jsonl'
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
# All heredocs below use << 'WRAPPER' (single-quoted) so the script body is
# written verbatim — variables resolve at *runtime* when the wrapper executes.
# ─────────────────────────────────────────────────────────────────────────────

# ── Designer ──────────────────────────────────────────────────────────────────
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
"$PYTHON" "${SCRIPT_DIR}/scripts/designer_agent.py" \
    --model "${MODEL_DESIGNER}" \
    --design-dir "${WORKSPACE_DIR}/design" \
    --token-log "${SENTINEL_DIR}/tokens/designer.jsonl" \
    --run-log "${RUN_LOG}"
echo ""
echo "[Designer Agent complete]"
WRAPPER

# ── Business Analyst ──────────────────────────────────────────────────────────
# Watches design/ for *.new.md files produced by the Designer Agent.
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
echo "Watching ${DESIGN_DIR}/ for *.new.md files..."
echo ""

while true; do
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo "[Business Analyst] Pipeline complete — exiting."
        break
    fi

    shopt -s nullglob
    for design_file in "$DESIGN_DIR"/*.new.md; do
        processed="${design_file%.new.md}.processed.md"
        feature="$(basename "${design_file%.new.md}")"

        echo "[Business Analyst] New design: ${feature} — decomposing into stories..."
        echo ""
        "$PYTHON" "${SCRIPT_DIR}/scripts/business_analyst_agent.py" \
            --design "$design_file" \
            --stories-dir "${STORIES_DIR}" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_BA}" \
            --token-log "${SENTINEL_DIR}/tokens/ba.jsonl" \
            --run-log "${RUN_LOG}"

        mv "$design_file" "$processed"
        echo ""
        echo "[Business Analyst] ${feature} → processed. Resuming watch..."
        echo ""
    done
    shopt -u nullglob

    sleep 5
done
WRAPPER

# ── Project Initialiser ───────────────────────────────────────────────────────
# Skips when workspace/CLAUDE.md already exists.
# Otherwise waits for the first *.new.md design file, then scaffolds — exactly once.
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

if [ -f "${WORKSPACE_DIR}/CLAUDE.md" ]; then
    echo "workspace/CLAUDE.md already exists — skipping scaffold step."
    exit 0
fi

echo "Waiting for a design/*.new.md file..."

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
"$PYTHON" "${SCRIPT_DIR}/scripts/project_initialiser_agent.py" \
    --design "${design_file}" \
    --workspace-dir "${WORKSPACE_DIR}" \
    --model "${MODEL_PI}" \
    --token-log "${SENTINEL_DIR}/tokens/pi.jsonl" \
    --run-log "${RUN_LOG}"
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
    "${PYTHON}" "${SCRIPT_DIR}/scripts/junior_coding_agent.py" \
        --stories-dir "${STORIES_DIR}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_JUNIOR}" \
        --token-log "${SENTINEL_DIR}/tokens/junior_${AGENT_ID}.jsonl" \
        --run-log "${RUN_LOG}"
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
        sleep 2   # let renamed story files settle before resuming
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
    chmod +x "$SENTINEL_DIR/run_junior_${i}.sh"
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
    "${PYTHON}" "${SCRIPT_DIR}/scripts/senior_coding_agent.py" \
        --stories-dir "${STORIES_DIR}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_SENIOR}" \
        --token-log "${SENTINEL_DIR}/tokens/senior_${AGENT_ID}.jsonl" \
        --run-log "${RUN_LOG}"
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
        sleep 2   # let renamed story files settle before resuming
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
    chmod +x "$SENTINEL_DIR/run_senior_${i}.sh"
done

# ── Story Orchestrator ────────────────────────────────────────────────────────
# Watches stories/ for bare STORY-NNN.md files, resolves dependencies, and
# renames them to STORY-NNN.[complexity].ready.md when all deps are done.
cat > "$SENTINEL_DIR/run_orchestrator.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Story Orchestrator\007'
source "$(dirname "$0")/config.sh"
# shellcheck disable=SC1091
source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║      Story Orchestrator          ║"
echo "╚══════════════════════════════════╝"
echo "Watches stories/ — marks stories ready when dependencies are met."
echo ""
"${PYTHON}" "${SCRIPT_DIR}/scripts/story_orchestrator.py" \
    --stories-dir "${STORIES_DIR}"
echo ""
echo "[Story Orchestrator exited]"
WRAPPER

# ── Watchdog ──────────────────────────────────────────────────────────────────
# Resets stale *.working.md files (idle > 10 min) back to *.ready.md.
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
# Runs continuously — wakes on HALT, triages failed stories with the user,
# then waits again. Exits cleanly when pipeline_complete is written.
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
    "${PYTHON}" "${SCRIPT_DIR}/scripts/story_reviewer_agent.py" \
        --stories-dir "${STORIES_DIR}" \
        --model "${MODEL_REVIEWER}" \
        --token-log "${SENTINEL_DIR}/tokens/reviewer.jsonl"
    echo ""
    echo "[Story Reviewer] Session complete — resuming watch."
    echo ""
done
WRAPPER

chmod +x \
    "$SENTINEL_DIR/run_designer.sh" \
    "$SENTINEL_DIR/run_ba.sh" \
    "$SENTINEL_DIR/run_pi.sh" \
    "$SENTINEL_DIR/run_orchestrator.sh" \
    "$SENTINEL_DIR/junior_coding_agent_body.sh" \
    "$SENTINEL_DIR/senior_coding_agent_body.sh" \
    "$SENTINEL_DIR/run_watchdog.sh" \
    "$SENTINEL_DIR/run_story_reviewer.sh"

# ─────────────────────────────────────────────────────────────────────────────
# Launch all windows simultaneously
# ─────────────────────────────────────────────────────────────────────────────
TOTAL=$(( N_JUNIOR_AGENTS + N_SENIOR_AGENTS + 6 ))
echo "Opening $TOTAL windows simultaneously ($N_JUNIOR_AGENTS junior + $N_SENIOR_AGENTS senior + 6 fixed agents)..."
echo ""

open_window "🎨 Designer Agent"        "$SENTINEL_DIR/run_designer.sh"
open_window "📋 Business Analyst"      "$SENTINEL_DIR/run_ba.sh"
open_window "🏗️  Project Initialiser"  "$SENTINEL_DIR/run_pi.sh"
open_window "🎯 Story Orchestrator"    "$SENTINEL_DIR/run_orchestrator.sh"
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
# Monitor — print status whenever it changes, and every ~30s regardless.
# Runs until Ctrl+C, which triggers _teardown via the trap below.
# Coding agents poll indefinitely so the pipeline is open-ended: the BA may
# write new stories at any time and agents pick them up automatically.
# ─────────────────────────────────────────────────────────────────────────────
echo "Monitoring pipeline (press Ctrl+C to shut down the team)..."
echo ""

# Count story files in a given state. Pass "unprocessed" for bare STORY-NNN.md
# files (no complexity/state suffix yet); or a state suffix like "ready"/"done".
_count_stories() {
    local state="$1"
    local count=0 f base
    if [[ "$state" == "unprocessed" ]]; then
        for f in "$STORIES_DIR"/STORY-*.md; do
            [[ -f "$f" ]] || continue
            base="$(basename "$f")"
            [[ "$base" =~ ^STORY-[0-9]+\.md$ ]] && (( count++ )) || true
        done
    else
        for f in "$STORIES_DIR"/STORY-*."${state}".md; do
            [[ -f "$f" ]] && (( count++ )) || true
        done
    fi
    echo "$count"
}

# Print per-agent token totals from JSONL log files (inline Python for portability).
_token_summary() {
    local tokens_dir="$SENTINEL_DIR/tokens"
    [ -d "$tokens_dir" ] || return 0
    shopt -s nullglob
    local logs=("$tokens_dir"/*.jsonl)
    shopt -u nullglob
    [ "${#logs[@]}" -eq 0 ] && return 0

    "$PYTHON" - "$tokens_dir" \
        "designer=${MODEL_DESIGNER}" \
        "ba=${MODEL_BA}" \
        "pi=${MODEL_PI}" \
        "junior=${MODEL_JUNIOR}" \
        "senior=${MODEL_SENIOR}" \
        "reviewer=${MODEL_REVIEWER}" <<'PYEOF'
import sys, json, os, glob

tokens_dir = sys.argv[1]
# Parse "agentprefix=model-name" args into a lookup dict
models = {}
for arg in sys.argv[2:]:
    if '=' in arg:
        k, v = arg.split('=', 1)
        models[k] = v

def get_model(agent):
    if agent in models:
        return models[agent]
    # junior_1, senior_2 etc. — strip the numeric suffix
    for prefix, model in models.items():
        if agent.startswith(prefix + '_') or agent == prefix:
            return model
    return ''

totals = {}
for path in sorted(glob.glob(os.path.join(tokens_dir, "*.jsonl"))):
    agent = os.path.basename(path).replace(".jsonl", "")
    inp = out = cache_r = cache_w = 0
    cost = 0.0
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    inp     += rec.get("input_tokens", 0)
                    out     += rec.get("output_tokens", 0)
                    cache_r += rec.get("cache_read_tokens", 0)
                    cache_w += rec.get("cache_write_tokens", 0)
                    cost    += rec.get("cost_usd", 0.0)
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    totals[agent] = (inp, out, cache_r, cache_w, cost)

if not totals:
    sys.exit(0)

grand_total_inp     = sum(t[0] for t in totals.values())
grand_total_out     = sum(t[1] for t in totals.values())
grand_total_cache_r = sum(t[2] for t in totals.values())
grand_total_cache_w = sum(t[3] for t in totals.values())
grand_total_cost    = sum(t[4] for t in totals.values())

print("  Tokens:")
for agent, (inp, out, cache_r, cache_w, cost) in totals.items():
    model = get_model(agent)
    model_note = f"  [{model}]" if model else ""
    cache_note = f"  cache r={cache_r:,} w={cache_w:,}" if cache_r or cache_w else ""
    cost_note = f"  cost=${cost:.4f}" if cost else ""
    print(f"    {agent:<20}  in={inp:>8,}  out={out:>7,}{cache_note}{cost_note}{model_note}")
grand_cache_note = f"  cache r={grand_total_cache_r:,} w={grand_total_cache_w:,}" if grand_total_cache_r or grand_total_cache_w else ""
print(f"    {'TOTAL':<20}  in={grand_total_inp:>8,}  out={grand_total_out:>7,}{grand_cache_note}  cost=${grand_total_cost:.4f}")
PYEOF
}

# On Ctrl+C / SIGTERM: signal all agents to exit, print final status and token report.
_teardown() {
    echo ""
    echo "Shutting down team..."
    touch "$SENTINEL_DIR/pipeline_complete"
    pkill -f "watchdog.sh" 2>/dev/null || true
    sleep 2
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║               Team shut down  👋                ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    bash "$SCRIPT_DIR/status.sh"
    echo ""
    _token_summary
    echo ""
    echo "  Generating run report..."
    report_path=$("$PYTHON" "$SCRIPT_DIR/run_report.py" \
        --run-log "$SENTINEL_DIR/run-log.jsonl" \
        --tokens-dir "$SENTINEL_DIR/tokens" \
        --output-dir "$WORKSPACE_DIR" 2>/dev/null) && \
        echo "  Run report written → $report_path" || \
        echo "  (Run report skipped — no log data)"
    rm -rf "$SENTINEL_DIR"
    exit 0
}

trap '_teardown' INT TERM

LAST_STATUS=""
TOKEN_TICK=0
while true; do
    unproc="$(_count_stories unprocessed)"
    ready="$(_count_stories ready)"
    working="$(_count_stories working)"
    done_n="$(_count_stories done)"
    failed="$(_count_stories failed)"
    halt_flag=$( [ -f "$STORIES_DIR/HALT" ] && echo "  ⚠ HALTED" || echo "" )

    STATUS="unproc=${unproc}  ready=${ready}  working=${working}  done=${done_n}  failed=${failed}${halt_flag}"
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        echo ""
        echo "  $(date '+%H:%M:%S')  stories: $STATUS"
        _token_summary
        LAST_STATUS="$STATUS"
        TOKEN_TICK=0
    fi

    # Also refresh token summary every ~30s even when story counts haven't changed.
    TOKEN_TICK=$(( TOKEN_TICK + 1 ))
    if [ "$TOKEN_TICK" -ge 3 ]; then
        echo ""
        echo "  $(date '+%H:%M:%S')  stories: $STATUS"
        _token_summary
        TOKEN_TICK=0
    fi

    sleep 10
done
