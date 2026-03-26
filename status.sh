#!/usr/bin/env bash
# Prints a live summary of all story states in stories/

STORIES_DIR="$(dirname "$0")/stories"

count_and_list() {
    local pattern="$1"
    local files
    files=$(find "$STORIES_DIR" -maxdepth 1 -name "$pattern" 2>/dev/null | sort)
    local count
    count=$(echo "$files" | grep -c . 2>/dev/null || echo 0)
    if [ -z "$files" ]; then
        count=0
    fi
    local names
    names=$(echo "$files" | xargs -I{} basename {} 2>/dev/null | tr '\n' ' ' | sed 's/ $//')
    echo "$count" "$names"
}

pending_data=$(count_and_list "STORY-*.md")
working_data=$(count_and_list "STORY-*.working.md")
done_data=$(count_and_list "STORY-*.done.md")
failed_data=$(count_and_list "STORY-*.failed.md")
reviewing_data=$(count_and_list "STORY-*.reviewing.md")

halt="no"
[ -f "$STORIES_DIR/HALT" ] && halt="YES"

printf "\n"
printf "  %-12s %s\n" "pending"   "$pending_data"
printf "  %-12s %s\n" "working"   "$working_data"
printf "  %-12s %s\n" "done"      "$done_data"
printf "  %-12s %s\n" "failed"    "$failed_data"
printf "  %-12s %s\n" "reviewing" "$reviewing_data"
printf "  %-12s %s\n" "HALT"      "$halt"
printf "\n"
