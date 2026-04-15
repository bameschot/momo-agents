#!/usr/bin/env bash
# start-team.sh — opens ALL agents simultaneously, each in its own console window.
# Agents self-coordinate via the filesystem; no window needs to wait for another.
#
# Usage: ./start-team.sh --workspace <path> [options]
#        Options: [--agent-type claude|ollama]          (global default for all roles)
#                 [--designer-agent-type claude|ollama]  (override for Designer)
#                 [--ba-agent-type claude|ollama]        (override for Business Analyst)
#                 [--pi-agent-type claude|ollama]        (override for Project Initialiser)
#                 [--junior-agent-type claude|ollama]    (override for Junior Coding Agents)
#                 [--senior-agent-type claude|ollama]    (override for Senior Coding Agents)
#                 [--resolver-agent-type claude|ollama]  (override for Story Resolver Agent)
#                 [--junior-agents N] [--senior-agents N]
#                 [--model-designer M] [--model-ba M] [--model-pi M]
#                 [--model-junior M] [--model-senior M] [--model-resolver M]
#                 [--ollama-host URL]
#
# Supported terminal environments (auto-detected in priority order):
#   macOS   : Terminal.app via osascript
#   Linux   : gnome-terminal · konsole · xfce4-terminal · mate-terminal · xterm
#   Fallback: tmux (new session "momo-agents"; attach with: tmux attach -t momo-agents)

set -euo pipefail

# ─────────────────────────────────────────────────────────────────────────────
# Paths — only the script's own location is known at this point.
# WORKSPACE_DIR and its subdirs are resolved after argument parsing.
# ─────────────────────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ─────────────────────────────────────────────────────────────────────────────
# Defaults
# ─────────────────────────────────────────────────────────────────────────────
WORKSPACE_DIR=""
AGENT_TYPE="claude"
OLLAMA_HOST="http://localhost:11434"
N_JUNIOR_AGENTS=2
N_SENIOR_AGENTS=1

# Per-role agent type overrides — empty means "inherit from AGENT_TYPE"
AGENT_TYPE_DESIGNER=""
AGENT_TYPE_BA=""
AGENT_TYPE_PI=""
AGENT_TYPE_JUNIOR=""
AGENT_TYPE_SENIOR=""
AGENT_TYPE_RESOLVER=""
AGENT_TYPE_MERGER=""

# Model placeholders — finalised after arg parsing once per-role agent types are known.
MODEL_DESIGNER=""
MODEL_BA=""
MODEL_PI=""
MODEL_JUNIOR=""
MODEL_SENIOR=""
MODEL_RESOLVER=""
MODEL_MERGER=""

# Claude effort levels per role — only applied when agent type is claude.
CLAUDE_EFFORT_DESIGNER="medium"
CLAUDE_EFFORT_BA="medium"
CLAUDE_EFFORT_PI="medium"
CLAUDE_EFFORT_JUNIOR="medium"
CLAUDE_EFFORT_SENIOR="medium"
CLAUDE_EFFORT_RESOLVER="medium"
CLAUDE_EFFORT_MERGER="medium"

# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────
args=("$@")
for ((i = 0; i < ${#args[@]}; i++)); do
    case "${args[$i]}" in
        --workspace=*)              WORKSPACE_DIR="${args[$i]#*=}" ;;
        --workspace)                WORKSPACE_DIR="${args[$((i + 1))]:-}" ;;
        --agent-type=*)             AGENT_TYPE="${args[$i]#*=}" ;;
        --agent-type)               AGENT_TYPE="${args[$((i + 1))]:-claude}" ;;
        --designer-agent-type=*)    AGENT_TYPE_DESIGNER="${args[$i]#*=}" ;;
        --designer-agent-type)      AGENT_TYPE_DESIGNER="${args[$((i + 1))]:-}" ;;
        --ba-agent-type=*)          AGENT_TYPE_BA="${args[$i]#*=}" ;;
        --ba-agent-type)            AGENT_TYPE_BA="${args[$((i + 1))]:-}" ;;
        --pi-agent-type=*)          AGENT_TYPE_PI="${args[$i]#*=}" ;;
        --pi-agent-type)            AGENT_TYPE_PI="${args[$((i + 1))]:-}" ;;
        --junior-agent-type=*)      AGENT_TYPE_JUNIOR="${args[$i]#*=}" ;;
        --junior-agent-type)        AGENT_TYPE_JUNIOR="${args[$((i + 1))]:-}" ;;
        --senior-agent-type=*)      AGENT_TYPE_SENIOR="${args[$i]#*=}" ;;
        --senior-agent-type)        AGENT_TYPE_SENIOR="${args[$((i + 1))]:-}" ;;
        --ollama-host=*)            OLLAMA_HOST="${args[$i]#*=}" ;;
        --ollama-host)              OLLAMA_HOST="${args[$((i + 1))]:-http://localhost:11434}" ;;
        --junior-agents=*)          N_JUNIOR_AGENTS="${args[$i]#*=}" ;;
        --junior-agents)            N_JUNIOR_AGENTS="${args[$((i + 1))]:-2}" ;;
        --senior-agents=*)          N_SENIOR_AGENTS="${args[$i]#*=}" ;;
        --senior-agents)            N_SENIOR_AGENTS="${args[$((i + 1))]:-1}" ;;
        --model-designer=*)         MODEL_DESIGNER="${args[$i]#*=}" ;;
        --model-designer)           MODEL_DESIGNER="${args[$((i + 1))]:-}" ;;
        --model-ba=*)               MODEL_BA="${args[$i]#*=}" ;;
        --model-ba)                 MODEL_BA="${args[$((i + 1))]:-}" ;;
        --model-pi=*)               MODEL_PI="${args[$i]#*=}" ;;
        --model-pi)                 MODEL_PI="${args[$((i + 1))]:-}" ;;
        --model-junior=*)           MODEL_JUNIOR="${args[$i]#*=}" ;;
        --model-junior)             MODEL_JUNIOR="${args[$((i + 1))]:-}" ;;
        --model-senior=*)           MODEL_SENIOR="${args[$i]#*=}" ;;
        --model-senior)             MODEL_SENIOR="${args[$((i + 1))]:-}" ;;
        --model-resolver=*)         MODEL_RESOLVER="${args[$i]#*=}" ;;
        --model-resolver)           MODEL_RESOLVER="${args[$((i + 1))]:-}" ;;
        --resolver-agent-type=*)    AGENT_TYPE_RESOLVER="${args[$i]#*=}" ;;
        --resolver-agent-type)      AGENT_TYPE_RESOLVER="${args[$((i + 1))]:-}" ;;
        --model-merger=*)           MODEL_MERGER="${args[$i]#*=}" ;;
        --model-merger)             MODEL_MERGER="${args[$((i + 1))]:-}" ;;
        --merger-agent-type=*)      AGENT_TYPE_MERGER="${args[$i]#*=}" ;;
        --merger-agent-type)        AGENT_TYPE_MERGER="${args[$((i + 1))]:-}" ;;
        --designer-claude-effort=*) CLAUDE_EFFORT_DESIGNER="${args[$i]#*=}" ;;
        --designer-claude-effort)   CLAUDE_EFFORT_DESIGNER="${args[$((i + 1))]:-medium}" ;;
        --ba-claude-effort=*)       CLAUDE_EFFORT_BA="${args[$i]#*=}" ;;
        --ba-claude-effort)         CLAUDE_EFFORT_BA="${args[$((i + 1))]:-medium}" ;;
        --pi-claude-effort=*)       CLAUDE_EFFORT_PI="${args[$i]#*=}" ;;
        --pi-claude-effort)         CLAUDE_EFFORT_PI="${args[$((i + 1))]:-medium}" ;;
        --junior-claude-effort=*)   CLAUDE_EFFORT_JUNIOR="${args[$i]#*=}" ;;
        --junior-claude-effort)     CLAUDE_EFFORT_JUNIOR="${args[$((i + 1))]:-medium}" ;;
        --senior-claude-effort=*)   CLAUDE_EFFORT_SENIOR="${args[$i]#*=}" ;;
        --senior-claude-effort)     CLAUDE_EFFORT_SENIOR="${args[$((i + 1))]:-medium}" ;;
        --resolver-claude-effort=*) CLAUDE_EFFORT_RESOLVER="${args[$i]#*=}" ;;
        --resolver-claude-effort)   CLAUDE_EFFORT_RESOLVER="${args[$((i + 1))]:-medium}" ;;
        --merger-claude-effort=*)   CLAUDE_EFFORT_MERGER="${args[$i]#*=}" ;;
        --merger-claude-effort)     CLAUDE_EFFORT_MERGER="${args[$((i + 1))]:-medium}" ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Validate global agent type
# ─────────────────────────────────────────────────────────────────────────────
if [ "$AGENT_TYPE" != "claude" ] && [ "$AGENT_TYPE" != "ollama" ]; then
    echo "Error: --agent-type must be 'claude' or 'ollama', got: '$AGENT_TYPE'" >&2
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Resolve per-role agent types — default to global AGENT_TYPE when not set.
# Validate each.
# ─────────────────────────────────────────────────────────────────────────────
AGENT_TYPE_DESIGNER="${AGENT_TYPE_DESIGNER:-$AGENT_TYPE}"
AGENT_TYPE_BA="${AGENT_TYPE_BA:-$AGENT_TYPE}"
AGENT_TYPE_PI="${AGENT_TYPE_PI:-$AGENT_TYPE}"
AGENT_TYPE_JUNIOR="${AGENT_TYPE_JUNIOR:-$AGENT_TYPE}"
AGENT_TYPE_SENIOR="${AGENT_TYPE_SENIOR:-$AGENT_TYPE}"
AGENT_TYPE_RESOLVER="${AGENT_TYPE_RESOLVER:-$AGENT_TYPE}"
AGENT_TYPE_MERGER="${AGENT_TYPE_MERGER:-$AGENT_TYPE}"

for _role_var in AGENT_TYPE_DESIGNER AGENT_TYPE_BA AGENT_TYPE_PI AGENT_TYPE_JUNIOR AGENT_TYPE_SENIOR AGENT_TYPE_RESOLVER AGENT_TYPE_MERGER; do
    _val="${!_role_var}"
    if [ "$_val" != "claude" ] && [ "$_val" != "ollama" ]; then
        echo "Error: --${_role_var/AGENT_TYPE_/} must be 'claude' or 'ollama', got: '$_val'" >&2
        exit 1
    fi
done

# ─────────────────────────────────────────────────────────────────────────────
# Per-role model defaults — derived from each role's own agent type.
# ─────────────────────────────────────────────────────────────────────────────
_default_model() {
    local agent_type="$1" role="$2"
    if [ "$agent_type" = "claude" ]; then
        case "$role" in
            junior|pi|merger) echo "claude-haiku-4-5-20251001" ;;
            *)         echo "claude-sonnet-4-6" ;;
        esac
    else
        echo "qwen3.5:4b"
    fi
}

MODEL_DESIGNER="${MODEL_DESIGNER:-$(_default_model "$AGENT_TYPE_DESIGNER" designer)}"
MODEL_BA="${MODEL_BA:-$(_default_model "$AGENT_TYPE_BA" ba)}"
MODEL_PI="${MODEL_PI:-$(_default_model "$AGENT_TYPE_PI" pi)}"
MODEL_JUNIOR="${MODEL_JUNIOR:-$(_default_model "$AGENT_TYPE_JUNIOR" junior)}"
MODEL_SENIOR="${MODEL_SENIOR:-$(_default_model "$AGENT_TYPE_SENIOR" senior)}"
MODEL_RESOLVER="${MODEL_RESOLVER:-$(_default_model "$AGENT_TYPE_RESOLVER" resolver)}"
MODEL_MERGER="${MODEL_MERGER:-$(_default_model "$AGENT_TYPE_MERGER" merger)}"

if [ -z "$WORKSPACE_DIR" ]; then
    echo "Usage: $0 --workspace <path> [options]"
    echo ""
    echo "  --workspace <path>          Path to the workspace directory (required)."
    echo "                              Created automatically (with git init) if it does not exist."
    echo ""
    echo "  --agent-type TYPE           Global agent backend: 'claude' (default) or 'ollama'."
    echo "                              Applies to all roles unless overridden per role below."
    echo "  --ollama-host URL           Ollama API base URL (default: http://localhost:11434)."
    echo "                              Used by any role configured as ollama."
    echo ""
    echo "  Per-role agent type overrides (each defaults to --agent-type):"
    echo "  --designer-agent-type TYPE  Agent type for the Designer"
    echo "  --ba-agent-type TYPE        Agent type for the Business Analyst"
    echo "  --pi-agent-type TYPE        Agent type for the Project Initialiser"
    echo "  --junior-agent-type TYPE    Agent type for Junior Coding Agents"
    echo "  --senior-agent-type TYPE    Agent type for Senior Coding Agents"
    echo "  --resolver-agent-type TYPE  Agent type for Story Resolver Agent"
    echo "  --merger-agent-type TYPE    Agent type for Merger Agent"
    echo ""
    echo "  --junior-agents N           Junior Coding Agents to spawn — handle easy stories    (default: 2)"
    echo "  --senior-agents N           Senior Coding Agents to spawn — handle medium/hard     (default: 1)"
    echo ""
    echo "  --model-designer M          Model for Designer Agent"
    echo "  --model-ba M                Model for Business Analyst"
    echo "  --model-pi M                Model for Project Initialiser"
    echo "  --model-junior M            Model for Junior Coding Agents"
    echo "  --model-senior M            Model for Senior Coding Agents"
    echo "  --model-resolver M          Model for Story Resolver Agent (default: claude-sonnet-4-6)"
    echo "  --model-merger M            Model for Merger Agent (default: claude-haiku-4-5-20251001)"
    echo ""
    echo "  claude defaults:  designer/ba/senior/resolver/merger=claude-sonnet-4-6"
    echo "                    junior/pi=claude-haiku-4-5-20251001"
    echo "  ollama defaults:  all roles=qwen3.5:4b"
    echo ""
    echo "  Claude effort levels (only applied when agent type is claude):"
    echo "  --designer-claude-effort E  Effort for Designer (default: medium)"
    echo "  --ba-claude-effort E        Effort for Business Analyst (default: medium)"
    echo "  --pi-claude-effort E        Effort for Project Initialiser (default: medium)"
    echo "  --junior-claude-effort E    Effort for Junior Coding Agents (default: medium)"
    echo "  --senior-claude-effort E    Effort for Senior Coding Agents (default: medium)"
    echo "  --resolver-claude-effort E  Effort for Story Resolver Agent (default: medium)"
    echo "  --merger-claude-effort E    Effort for Merger Agent (default: medium)"
    echo "  Valid values: low, medium, high, max"
    exit 1
fi

# ─────────────────────────────────────────────────────────────────────────────
# Workspace — resolve to absolute path, create if needed, validate git repo
# ─────────────────────────────────────────────────────────────────────────────
if [[ "$WORKSPACE_DIR" != /* ]]; then
    WORKSPACE_DIR="$(pwd)/$WORKSPACE_DIR"
fi

if [ ! -d "$WORKSPACE_DIR" ]; then
    echo ""
    echo "  Workspace '${WORKSPACE_DIR}' does not exist."
    read -rp "  Create it? [y/N] " _ws_answer
    echo ""
    if [[ "${_ws_answer:-}" =~ ^[Yy]$ ]]; then
        mkdir -p "$WORKSPACE_DIR"
        git -C "$WORKSPACE_DIR" init --quiet
        echo ".sentinels/" > "$WORKSPACE_DIR/.gitignore"
        echo "  Workspace created and git repository initialised: ${WORKSPACE_DIR}"
        echo ""
    else
        echo "  Aborting — workspace directory is required."
        exit 1
    fi
elif [ ! -d "$WORKSPACE_DIR/.git" ]; then
    echo ""
    echo "  Warning: workspace '${WORKSPACE_DIR}' exists but is not a git repository."
    echo "  Coding agents that commit changes may fail."
    echo "  Run: git init '${WORKSPACE_DIR}'"
    echo ""
fi

# Derive subdirectory paths and display name from the workspace
FEATURE="$(basename "$WORKSPACE_DIR")"
DESIGN_DIR="$WORKSPACE_DIR/design"
STORIES_DIR="$WORKSPACE_DIR/stories"
SENTINEL_DIR="$WORKSPACE_DIR/.sentinels"

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
TEAM_START_TIME="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
mkdir -p "$SENTINEL_DIR" "$SENTINEL_DIR/agent_conversation_logs"
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
AGENT_TYPE='$AGENT_TYPE'
AGENT_TYPE_DESIGNER='$AGENT_TYPE_DESIGNER'
AGENT_TYPE_BA='$AGENT_TYPE_BA'
AGENT_TYPE_PI='$AGENT_TYPE_PI'
AGENT_TYPE_JUNIOR='$AGENT_TYPE_JUNIOR'
AGENT_TYPE_SENIOR='$AGENT_TYPE_SENIOR'
AGENT_TYPE_RESOLVER='$AGENT_TYPE_RESOLVER'
AGENT_TYPE_MERGER='$AGENT_TYPE_MERGER'
OLLAMA_HOST='$OLLAMA_HOST'
ANTHROPIC_API_KEY='${ANTHROPIC_API_KEY:-}'
MODEL_DESIGNER='$MODEL_DESIGNER'
MODEL_BA='$MODEL_BA'
MODEL_PI='$MODEL_PI'
MODEL_JUNIOR='$MODEL_JUNIOR'
MODEL_SENIOR='$MODEL_SENIOR'
MODEL_RESOLVER='$MODEL_RESOLVER'
MODEL_MERGER='$MODEL_MERGER'
CLAUDE_EFFORT_DESIGNER='$CLAUDE_EFFORT_DESIGNER'
CLAUDE_EFFORT_BA='$CLAUDE_EFFORT_BA'
CLAUDE_EFFORT_PI='$CLAUDE_EFFORT_PI'
CLAUDE_EFFORT_JUNIOR='$CLAUDE_EFFORT_JUNIOR'
CLAUDE_EFFORT_SENIOR='$CLAUDE_EFFORT_SENIOR'
CLAUDE_EFFORT_RESOLVER='$CLAUDE_EFFORT_RESOLVER'
CLAUDE_EFFORT_MERGER='$CLAUDE_EFFORT_MERGER'
RUN_LOG='$SENTINEL_DIR/run-log.jsonl'
CONV_LOG_DIR='$SENTINEL_DIR/agent_conversation_logs'
CONFIG

# ─────────────────────────────────────────────────────────────────────────────
# Banner
# ─────────────────────────────────────────────────────────────────────────────
WS_STATE="$(_workspace_initialized && echo "already initialised (PI will skip)" || echo "empty (PI will scaffold)")"

# Helper: show role type only when it differs from the global agent type
_role_type_note() {
    local role_type="$1"
    if [ "$role_type" != "$AGENT_TYPE" ]; then
        echo " ($role_type)"
    fi
}

echo "╔══════════════════════════════════════════════════╗"
echo "║           momo-agents  ·  start-team             ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""
echo "  Feature        : $FEATURE"
echo "  Agent Type     : $AGENT_TYPE  (global default)"
echo "  Ollama Host    : $OLLAMA_HOST"
echo "  Junior Agents  : $N_JUNIOR_AGENTS"
echo "  Senior Agents  : $N_SENIOR_AGENTS"
echo "  Python         : $PYTHON"
echo "  Terminal       : $TERMINAL"
echo "  Workspace      : $WS_STATE"
echo ""
echo "  Roles:"
echo "    Designer   : [$AGENT_TYPE_DESIGNER] $MODEL_DESIGNER"
echo "    BA         : [$AGENT_TYPE_BA] $MODEL_BA"
echo "    PI         : [$AGENT_TYPE_PI] $MODEL_PI"
echo "    Junior     : [$AGENT_TYPE_JUNIOR] $MODEL_JUNIOR"
echo "    Senior     : [$AGENT_TYPE_SENIOR] $MODEL_SENIOR"
echo "    Resolver   : [$AGENT_TYPE_RESOLVER] $MODEL_RESOLVER"
echo "    Merger     : [$AGENT_TYPE_MERGER] $MODEL_MERGER"
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
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║        Designer Agent            ║"
echo "╚══════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_DESIGNER}"
echo "  Model : ${MODEL_DESIGNER}"
echo ""
echo "Ask clarifying questions then type 'write' to produce the design file."
echo ""
if [ "$AGENT_TYPE_DESIGNER" = "ollama" ]; then
    "$PYTHON" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_designer_agent.py" \
        --model "${MODEL_DESIGNER}" \
        --ollama-host "${OLLAMA_HOST}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "ollama-designer"
else
    "$PYTHON" "${SCRIPT_DIR}/scripts/claude_agents/claude_designer_agent.py" \
        --model "${MODEL_DESIGNER}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "designer" \
        --effort "${CLAUDE_EFFORT_DESIGNER}"
fi
echo ""
echo "[Designer Agent complete]"
WRAPPER

# ── Business Analyst ──────────────────────────────────────────────────────────
# Watches design/ for *.new.md files produced by the Designer Agent.
# The Python agent handles polling, processing, and renaming internally.
cat > "$SENTINEL_DIR/run_ba.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Business Analyst\007'
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║      Business Analyst Agent      ║"
echo "╚══════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_BA}"
echo "  Model : ${MODEL_BA}"
echo ""

if [ "$AGENT_TYPE_BA" = "ollama" ]; then
    "$PYTHON" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_business_analyst_agent.py" \
        --design-dir "${DESIGN_DIR}" \
        --stories-dir "${STORIES_DIR}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_BA}" \
        --ollama-host "${OLLAMA_HOST}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "ollama-business-analyst"
else
    "$PYTHON" "${SCRIPT_DIR}/scripts/claude_agents/claude_business_analyst_agent.py" \
        --design-dir "${DESIGN_DIR}" \
        --stories-dir "${STORIES_DIR}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_BA}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "business-analyst" \
        --effort "${CLAUDE_EFFORT_BA}"
fi
WRAPPER

# ── Project Initialiser ───────────────────────────────────────────────────────
# Skips when workspace/CLAUDE.md already exists.
# Waits for the first *.new.md design file, then scaffolds — exactly once.
cat > "$SENTINEL_DIR/run_pi.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Project Initialiser\007'
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║    Project Initialiser Agent     ║"
echo "╚══════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_PI}"
echo "  Model : ${MODEL_PI}"
echo ""

if [ -f "${WORKSPACE_DIR}/CLAUDE.md" ]; then
    echo "${WORKSPACE_DIR}/CLAUDE.md already exists — skipping scaffold step."
    exit 0
fi

echo "Waiting for ${DESIGN_DIR}/*.new.md..."

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
if [ "$AGENT_TYPE_PI" = "ollama" ]; then
    "$PYTHON" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_project_initialiser_agent.py" \
        --design "${design_file}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_PI}" \
        --ollama-host "${OLLAMA_HOST}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "ollama-project-initialiser"
else
    "$PYTHON" "${SCRIPT_DIR}/scripts/claude_agents/claude_project_initialiser_agent.py" \
        --design "${design_file}" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_PI}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "project-initialiser" \
        --effort "${CLAUDE_EFFORT_PI}"
fi
echo ""
echo "[Project Initialiser Agent complete]"
WRAPPER

# ── Junior Coding Agent (shared body, parameterised by $AGENT_ID) ────────────
# Claims easy stories only. Waits for PI to complete and for stories to exist.
cat > "$SENTINEL_DIR/junior_coding_agent_body.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"
# AGENT_ID is exported by the per-agent stub that execs this file.

printf "\033]0;Junior Coding Agent ${AGENT_ID} [easy]\007"
echo "╔══════════════════════════════════╗"
echo "║   Junior Coding Agent ${AGENT_ID} [easy]  ║"
echo "╚══════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_JUNIOR}"
echo "  Model : ${MODEL_JUNIOR}"
echo ""
echo "Handles: easy stories"
echo "Waiting for workspace/CLAUDE.md..."

while [ ! -f "${WORKSPACE_DIR}/CLAUDE.md" ]; do sleep 3; done

echo "Waiting for stories..."
while [ "$(find "${STORIES_DIR}" -maxdepth 1 -name 'STORY-*.md' \
           2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]; do
    sleep 3
done

echo "Prerequisites ready — starting agent loop."
echo ""

while true; do
    if [ "$AGENT_TYPE_JUNIOR" = "ollama" ]; then
        "${PYTHON}" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_junior_coding_agent.py" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_JUNIOR}" \
            --ollama-host "${OLLAMA_HOST}" \
            --conv-log-dir "${CONV_LOG_DIR}" \
            --run-log "${RUN_LOG}" \
            --agent-name "ollama-junior-coding-agent-${AGENT_ID}"
    else
        "${PYTHON}" "${SCRIPT_DIR}/scripts/claude_agents/claude_junior_coding_agent.py" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_JUNIOR}" \
            --conv-log-dir "${CONV_LOG_DIR}" \
            --run-log "${RUN_LOG}" \
            --agent-name "junior-coding-agent-${AGENT_ID}" \
            --effort "${CLAUDE_EFFORT_JUNIOR}"
    fi
    EXIT_CODE=$?

    # Orchestrator wrote pipeline_complete — clean exit
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo ""
        echo "[Junior Coding Agent ${AGENT_ID}] Pipeline complete — exiting."
        break
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
cat > "$SENTINEL_DIR/senior_coding_agent_body.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"
# AGENT_ID is exported by the per-agent stub that execs this file.

printf "\033]0;Senior Coding Agent ${AGENT_ID} [medium/hard]\007"
echo "╔══════════════════════════════════════╗"
echo "║  Senior Coding Agent ${AGENT_ID} [medium/hard]  ║"
echo "╚══════════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_SENIOR}"
echo "  Model : ${MODEL_SENIOR}"
echo ""
echo "Handles: medium and hard stories"
echo "Waiting for workspace/CLAUDE.md..."

while [ ! -f "${WORKSPACE_DIR}/CLAUDE.md" ]; do sleep 3; done

echo "Waiting for stories..."
while [ "$(find "${STORIES_DIR}" -maxdepth 1 -name 'STORY-*.md' \
           2>/dev/null | wc -l | tr -d ' ')" -eq 0 ]; do
    sleep 3
done

echo "Prerequisites ready — starting agent loop."
echo ""

while true; do
    if [ "$AGENT_TYPE_SENIOR" = "ollama" ]; then
        "${PYTHON}" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_senior_coding_agent.py" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_SENIOR}" \
            --ollama-host "${OLLAMA_HOST}" \
            --conv-log-dir "${CONV_LOG_DIR}" \
            --run-log "${RUN_LOG}" \
            --agent-name "ollama-senior-coding-agent-${AGENT_ID}"
    else
        "${PYTHON}" "${SCRIPT_DIR}/scripts/claude_agents/claude_senior_coding_agent.py" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_SENIOR}" \
            --conv-log-dir "${CONV_LOG_DIR}" \
            --run-log "${RUN_LOG}" \
            --agent-name "senior-coding-agent-${AGENT_ID}" \
            --effort "${CLAUDE_EFFORT_SENIOR}"
    fi
    EXIT_CODE=$?

    # Orchestrator wrote pipeline_complete — clean exit
    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo ""
        echo "[Senior Coding Agent ${AGENT_ID}] Pipeline complete — exiting."
        break
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
# Agent-type agnostic — operates purely on the filesystem.
cat > "$SENTINEL_DIR/run_orchestrator.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Story Orchestrator\007'
source "$(dirname "$0")/config.sh"
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"

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

# ── Story Resolver Agent ──────────────────────────────────────────────────────
# Interactive agent — prompts the user when failed stories are found.
# Always Claude (interactive session); polls when no failed stories exist.
cat > "$SENTINEL_DIR/run_resolver.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Story Resolver Agent\007'
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║     Story Resolver Agent         ║"
echo "╚══════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_RESOLVER}"
echo "  Model : ${MODEL_RESOLVER}"
echo ""
echo "Scans for failed stories and guides you through resolution interactively."
echo "Commands during a session:"
echo "  'update the story' — apply agreed fixes and reset the story to ready  (claude mode)"
echo "  'skip'             — skip this story and scan for the next"
echo "  'exit'             — stop the resolver"
echo ""

if [ "$AGENT_TYPE_RESOLVER" = "ollama" ]; then
    "$PYTHON" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_story_resolver_agent.py" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_RESOLVER}" \
        --ollama-host "${OLLAMA_HOST}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "ollama-story-resolver"
else
    "$PYTHON" "${SCRIPT_DIR}/scripts/claude_agents/claude_story_resolver_agent.py" \
        --workspace-dir "${WORKSPACE_DIR}" \
        --model "${MODEL_RESOLVER}" \
        --conv-log-dir "${CONV_LOG_DIR}" \
        --run-log "${RUN_LOG}" \
        --agent-name "story-resolver" \
        --effort "${CLAUDE_EFFORT_RESOLVER}"
fi

echo ""
echo "[Story Resolver Agent complete]"
WRAPPER

# ── Merger Agent ──────────────────────────────────────────────────────────────
# Polls merge-queue/ for completed story zips; merges them into main in order.
cat > "$SENTINEL_DIR/run_merger.sh" << 'WRAPPER'
#!/usr/bin/env bash
set -euo pipefail
printf '\033]0;Merger Agent\007'
source "$(dirname "$0")/config.sh"
export ANTHROPIC_API_KEY
# shellcheck disable=SC1091
[ -f "${SCRIPT_DIR}/.venv/bin/activate" ] && source "${SCRIPT_DIR}/.venv/bin/activate"

echo "╔══════════════════════════════════╗"
echo "║        Merger Agent              ║"
echo "╚══════════════════════════════════╝"
echo "  Mode  : ${AGENT_TYPE_MERGER}"
echo "  Model : ${MODEL_MERGER}"
echo ""
echo "Polls merge-queue/ and merges completed stories into main in story order."
echo ""

while true; do
    if [ "$AGENT_TYPE_MERGER" = "ollama" ]; then
        "$PYTHON" "${SCRIPT_DIR}/scripts/ollama_agents/ollama_merger_agent.py" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_MERGER}" \
            --ollama-host "${OLLAMA_HOST}" \
            --conv-log-dir "${CONV_LOG_DIR}" \
            --run-log "${RUN_LOG}" \
            --agent-name "ollama-merger-agent"
    else
        "$PYTHON" "${SCRIPT_DIR}/scripts/claude_agents/claude_merger_agent.py" \
            --workspace-dir "${WORKSPACE_DIR}" \
            --model "${MODEL_MERGER}" \
            --conv-log-dir "${CONV_LOG_DIR}" \
            --run-log "${RUN_LOG}" \
            --agent-name "merger-agent" \
            --effort "${CLAUDE_EFFORT_MERGER}"
    fi
    EXIT_CODE=$?

    if [ -f "${SENTINEL_DIR}/pipeline_complete" ]; then
        echo ""
        echo "[Merger Agent] Pipeline complete — exiting."
        break
    fi

    if [ $EXIT_CODE -ne 0 ]; then
        echo ""
        echo "[Merger Agent] Agent exited with code $EXIT_CODE — retrying in 10s..."
        sleep 10
    fi
done

echo ""
echo "[Merger Agent finished]"
WRAPPER

chmod +x \
    "$SENTINEL_DIR/run_designer.sh" \
    "$SENTINEL_DIR/run_ba.sh" \
    "$SENTINEL_DIR/run_pi.sh" \
    "$SENTINEL_DIR/run_orchestrator.sh" \
    "$SENTINEL_DIR/junior_coding_agent_body.sh" \
    "$SENTINEL_DIR/senior_coding_agent_body.sh" \
    "$SENTINEL_DIR/run_resolver.sh" \
    "$SENTINEL_DIR/run_merger.sh"

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
open_window "🔧 Story Resolver"        "$SENTINEL_DIR/run_resolver.sh"
open_window "🔀 Merger Agent"          "$SENTINEL_DIR/run_merger.sh"

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

# Count story files in a given state.
# "unprocessed" → bare STORY-NNN.md files in STORIES_DIR (not yet evaluated).
# "done"        → STORY-NNN.done.md files in STORIES_DIR (committed by Merger).
# "ready" / "working" / "failed" → files in the orchestrator dir (.sentinels/story-orchestrator/).
_count_stories() {
    local state="$1"
    local count=0 f base
    local orchestrator_dir="${SENTINEL_DIR}/story-orchestrator"
    if [[ "$state" == "unprocessed" ]]; then
        for f in "$STORIES_DIR"/STORY-*.md; do
            [[ -f "$f" ]] || continue
            base="$(basename "$f")"
            [[ "$base" =~ ^STORY-[0-9]+\.md$ ]] && (( count++ )) || true
        done
    elif [[ "$state" == "done" ]]; then
        for f in "$STORIES_DIR"/STORY-*."${state}".md; do
            [[ -f "$f" ]] && (( count++ )) || true
        done
    else
        for f in "$orchestrator_dir"/STORY-*."${state}".md; do
            [[ -f "$f" ]] && (( count++ )) || true
        done
    fi
    echo "$count"
}

# Print per-agent and total token/cost breakdown from the current run's conversation logs.
_token_totals() {
    local conv_dir="$SENTINEL_DIR/agent_conversation_logs"
    [ -d "$conv_dir" ] || { echo "  (no token data)"; return; }
    "$PYTHON" - "$conv_dir" << 'PYEOF'
import json, sys
from pathlib import Path
from collections import defaultdict

conv_log_dir = Path(sys.argv[1])
agents = defaultdict(lambda: {'input': 0, 'output': 0, 'cache_read': 0, 'cache_write': 0, 'cost': 0.0})
for f in sorted(conv_log_dir.glob('*_log.jsonl')):
    with open(f) as fh:
        for line in fh:
            try:
                e = json.loads(line)
            except Exception:
                continue
            role = e.get('role')
            agent = e.get('agent', f.stem.replace('_log', ''))
            if role == 'assistant':
                agents[agent]['input'] += e.get('input_tokens', 0)
                agents[agent]['output'] += e.get('output_tokens', 0)
                agents[agent]['cache_read'] += e.get('cache_read_tokens', 0)
                agents[agent]['cache_write'] += e.get('cache_write_tokens', 0)
            elif role == 'result':
                agents[agent]['cost'] += e.get('cost_usd', 0.0)

if not agents:
    print('  (no token data)')
    sys.exit(0)

total_in = total_out = total_cr = total_cw = 0
total_cost = 0.0
for agent, d in sorted(agents.items()):
    print(f'  {agent:<36}  in={d["input"]:>8,}  out={d["output"]:>7,}  cr={d["cache_read"]:>8,}  cw={d["cache_write"]:>8,}  ${d["cost"]:.4f}')
    total_in += d['input']
    total_out += d['output']
    total_cr += d['cache_read']
    total_cw += d['cache_write']
    total_cost += d['cost']
print()
print(f'  {"TOTAL":<36}  in={total_in:>8,}  out={total_out:>7,}  cr={total_cr:>8,}  cw={total_cw:>8,}  ${total_cost:.4f}')
PYEOF
}

# On Ctrl+C / SIGTERM: signal all agents to exit, print final status and generate the run report.
_teardown() {
    echo ""
    echo "Shutting down team..."
    touch "$SENTINEL_DIR/pipeline_complete"
    sleep 2
    echo ""
    echo "╔══════════════════════════════════════════════════╗"
    echo "║               Team shut down  👋                ║"
    echo "╚══════════════════════════════════════════════════╝"
    echo ""
    bash "$SCRIPT_DIR/status.sh" --workspace "$WORKSPACE_DIR"
    echo ""
    echo "  Exporting git log..."
    "$PYTHON" "$SCRIPT_DIR/git_log_exporter.py" \
        --repo "$WORKSPACE_DIR" \
        --start-date "$TEAM_START_TIME" \
        --output "$SENTINEL_DIR/git_log.jsonl" 2>/dev/null || true
    echo "  Generating run report..."
    report_path=$("$PYTHON" "$SCRIPT_DIR/run_report.py" \
        --run-log "$SENTINEL_DIR/run-log.jsonl" \
        --conv-log-dir "$SENTINEL_DIR/agent_conversation_logs" \
        --git-log "$SENTINEL_DIR/git_log.jsonl" \
        --output-dir "$WORKSPACE_DIR" 2>/dev/null) && \
        echo "  Run report written → $report_path" || \
        echo "  (Run report skipped — no log data)"
    rm -rf "$SENTINEL_DIR"
    exit 0
}

trap '_teardown' INT TERM

LAST_STATUS=""
while true; do
    unproc="$(_count_stories unprocessed)"
    ready="$(_count_stories ready)"
    working="$(_count_stories working)"
    done_n="$(_count_stories done)"
    failed="$(_count_stories failed)"

    STATUS="unproc=${unproc}  ready=${ready}  working=${working}  done=${done_n}  failed=${failed}"
    if [ "$STATUS" != "$LAST_STATUS" ]; then
        echo ""
        echo "  $(date '+%H:%M:%S')  stories: $STATUS"
        echo "  $(date '+%H:%M:%S')  tokens:"
        _token_totals
        LAST_STATUS="$STATUS"
    fi

    sleep 10
done
