#!/usr/bin/env bash
# Prints a live summary of all story states in stories/

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Optional --workspace <path> override (used by start-team.sh teardown)
WORKSPACE_OVERRIDE=""
for _arg in "$@"; do
    case "$_arg" in
        --workspace=*) WORKSPACE_OVERRIDE="${_arg#*=}" ;;
    esac
done
for ((i=1; i<=$#; i++)); do
    if [[ "${!i}" == "--workspace" ]]; then
        j=$((i+1)); WORKSPACE_OVERRIDE="${!j}"; break
    fi
done

if [ -n "$WORKSPACE_OVERRIDE" ]; then
    WORKSPACE_DIR="$WORKSPACE_OVERRIDE"
else
    WORKSPACE_DIR="$SCRIPT_DIR/workspace"
fi
STORIES_DIR="$WORKSPACE_DIR/stories"

# Python executable — prefer .venv
if [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    PYTHON="python"
fi

# count_state <grep-regex>
# Lists all files in STORIES_DIR whose basename matches the given extended regex.
count_state() {
    local regex="$1"
    local files
    files=$(find "$STORIES_DIR" -maxdepth 1 -type f 2>/dev/null \
        | grep -E "$regex" | sort)
    local count=0
    [ -n "$files" ] && count=$(echo "$files" | grep -c .)
    local names=""
    [ -n "$files" ] && names=$(echo "$files" | xargs -I{} basename {} 2>/dev/null \
        | tr '\n' ' ' | sed 's/ $//')
    echo "$count $names"
}

# Each regex anchors on the basename after the last /
unprocessed_data=$(count_state '/STORY-[0-9]+\.md$')
ready_data=$(count_state '/STORY-[0-9]+\.[a-z]+\.ready\.md$')
working_data=$(count_state '/STORY-[0-9]+\.[a-z]+\.working\.md$')
done_data=$(count_state '/STORY-[0-9]+\.[a-z]+\.done\.md$')
failed_data=$(count_state '/STORY-[0-9]+\.[a-z]+\.failed\.md$')
reviewing_data=$(count_state '/STORY-[0-9]+\.[a-z]+\.reviewing\.md$')

halt="no"
[ -f "$STORIES_DIR/HALT" ] && halt="YES"

printf "\n"
printf "  %-14s %s\n" "unprocessed"  "$unprocessed_data"
printf "  %-14s %s\n" "ready"        "$ready_data"
printf "  %-14s %s\n" "working"      "$working_data"
printf "  %-14s %s\n" "done"         "$done_data"
printf "  %-14s %s\n" "failed"       "$failed_data"
printf "  %-14s %s\n" "reviewing"    "$reviewing_data"
printf "  %-14s %s\n" "HALT"         "$halt"
printf "\n"

# Token / cost summary from conversation logs
CONV_LOG_DIR="$WORKSPACE_DIR/.sentinels/agent_conversation_logs"
if [ -d "$CONV_LOG_DIR" ]; then
    "$PYTHON" - "$CONV_LOG_DIR" << 'PYEOF'
import json, sys
from pathlib import Path
from collections import defaultdict

conv_log_dir = Path(sys.argv[1])
agents = defaultdict(lambda: {'input': 0, 'output': 0, 'cost': 0.0})
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
            elif role == 'result':
                agents[agent]['cost'] += e.get('cost_usd', 0.0)

if not agents:
    print('  (no token data)')
    sys.exit(0)

total_in = total_out = 0
total_cost = 0.0
for agent, d in sorted(agents.items()):
    print(f'  {agent:<36}  in={d["input"]:>8,}  out={d["output"]:>7,}  ${d["cost"]:.4f}')
    total_in += d['input']
    total_out += d['output']
    total_cost += d['cost']
print()
print(f'  {"TOTAL":<36}  in={total_in:>8,}  out={total_out:>7,}  ${total_cost:.4f}')
print()
PYEOF
fi
