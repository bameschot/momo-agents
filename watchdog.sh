#!/usr/bin/env bash
# Resets stories stuck in .working.md state for more than 10 minutes.
# Run in the background alongside Coding Agents.

STORIES_DIR="$(dirname "$0")/stories"
STALE_SECONDS=600  # 10 minutes

echo "[watchdog] started — checking every 60s, stale threshold ${STALE_SECONDS}s"

while true; do
    sleep 60

    now=$(date +%s)

    for working_file in "$STORIES_DIR"/STORY-*.working.md; do
        [ -f "$working_file" ] || continue

        last_modified=$(stat -f "%m" "$working_file" 2>/dev/null || stat -c "%Y" "$working_file" 2>/dev/null)
        age=$(( now - last_modified ))

        if [ "$age" -gt "$STALE_SECONDS" ]; then
            pending_file="${working_file%.working.md}.md"
            if mv "$working_file" "$pending_file" 2>/dev/null; then
                echo "[watchdog] reset stale story: $(basename "$working_file") → $(basename "$pending_file") (age: ${age}s)"
            fi
        fi
    done
done
