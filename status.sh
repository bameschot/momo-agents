#!/usr/bin/env bash
# Prints a live summary of all story states in stories/

STORIES_DIR="$(dirname "$0")/workspace/stories"

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
