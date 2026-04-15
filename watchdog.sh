#!/usr/bin/env bash
# Resets stories stuck in .working.md state for more than 10 minutes.
# Scans .sentinels/story-orchestrator/ where live story state is tracked.
# Skips stories that are already queued in .sentinels/merge-queue/ — those are
# awaiting the Merger Agent and should NOT be reset to .ready.
# Run in the background alongside Coding Agents.

STALE_SECONDS=600  # 10 minutes

# SENTINEL_DIR is exported by run_watchdog.sh (via config.sh).
# Fall back to a default relative to this script when run standalone.
SENTINEL_DIR="${SENTINEL_DIR:-$(dirname "$0")/workspace/.sentinels}"
ORCHESTRATOR_DIR="${SENTINEL_DIR}/story-orchestrator"
MERGE_QUEUE_DIR="${SENTINEL_DIR}/merge-queue"

echo "[watchdog] started — checking every 60s, stale threshold ${STALE_SECONDS}s"
echo "[watchdog] scanning ${ORCHESTRATOR_DIR}"

while true; do
    sleep 60

    now=$(date +%s)

    for working_file in "$ORCHESTRATOR_DIR"/STORY-*.working.md; do
        [ -f "$working_file" ] || continue

        # Extract STORY-NNN from the filename.
        basename_file="$(basename "$working_file")"
        story_id="${basename_file%%.*}"  # STORY-NNN

        # Skip stories that are already in the merge-queue — they are done
        # and waiting for the Merger Agent; resetting them would be wrong.
        if [ -f "${MERGE_QUEUE_DIR}/${story_id}.zip" ]; then
            continue
        fi

        last_modified=$(stat -f "%m" "$working_file" 2>/dev/null || stat -c "%Y" "$working_file" 2>/dev/null)
        age=$(( now - last_modified ))

        if [ "$age" -gt "$STALE_SECONDS" ]; then
            # STORY-NNN.[complexity].working.md → STORY-NNN.[complexity].ready.md
            ready_file="${working_file%.working.md}.ready.md"
            if mv "$working_file" "$ready_file" 2>/dev/null; then
                echo "[watchdog] reset stale story: $(basename "$working_file") → $(basename "$ready_file") (age: ${age}s)"
            fi
        fi
    done
done
