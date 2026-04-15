"""Merger Agent (Claude) — merges completed story workspaces into the main branch.

Workflow per story:
  1. Python: scan .sentinels/merge-queue/ for the lowest-numbered STORY-NNN.zip.
  2. Python: unzip it to .sentinels/merge-STORY-NNN/ (isolated staging area).
  3. LLM  : create a git branch, copy staged files into the workspace, commit,
             merge back to main, write outcome sentinel.
  4. Python: on success — mark the story .done.md in workspace/stories/.
  5. Python: delete staging dir and zip from the merge-queue.

Stories are always processed in ascending STORY-NNN order.
"""
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import (
    append_run_log,
    get_next_merge_story,
    load_role,
    mark_story_done_after_merge,
    resolve_path,
    unzip_workspace_for_merge,
    wait_for_workspace,
)
from conversation_logger import log_claude_message, print_claude_message

POLL_INTERVAL = 10  # seconds between polls when merge-queue is empty

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Merger Agent — merges story zips into main branch")
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--run-log",
        default="",
        help="Path to run-log.jsonl file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default="merger-agent",
        help="Name used to identify this agent in logs (default: merger-agent)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs (optional)",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "max"],
        help="Claude effort level (default: medium)",
    )
    return parser.parse_args()


def _build_task(
    story_id: str,
    extract_dir: Path,
    workspace_dir: Path,
    outcome_file: Path,
) -> str:
    branch_name = story_id.lower()  # e.g. story-003
    return (
        f"## Merge Task: {story_id}\n\n"
        f"Staged workspace (completed code to merge): {extract_dir}\n"
        f"Main workspace git repository            : {workspace_dir}\n"
        f"Outcome file                             : {outcome_file}\n\n"
        "## Steps\n\n"
        f"1. Check whether the main workspace has any commits yet:\n"
        f"   cd {workspace_dir} && git log --oneline -1\n"
        f"   If there are NO commits, create an initial commit first:\n"
        f"   git add -A && git commit -m 'chore: initial workspace scaffold'\n\n"
        f"2. Create a story branch from the latest main:\n"
        f"   cd {workspace_dir} && git checkout -b {branch_name}\n\n"
        f"3. Copy all files from the staged workspace into the main workspace\n"
        f"   (use cp -r; the staged dir has already had .git, stories, and design stripped):\n"
        f"   cp -r {extract_dir}/. {workspace_dir}/\n\n"
        f"4. Stage all changes:\n"
        f"   cd {workspace_dir} && git add -A\n\n"
        f"5. Check whether there is anything to commit:\n"
        f"   cd {workspace_dir} && git diff --cached --stat\n"
        f"   If there are staged changes, commit them:\n"
        f"   git commit -m 'feat: implement {story_id}'\n\n"
        f"6. Switch back to the main branch:\n"
        f"   cd {workspace_dir} && git checkout main || git checkout master\n\n"
        f"7. Merge the story branch:\n"
        f"   cd {workspace_dir} && git merge {branch_name} --no-ff -m 'merge: {story_id}'\n\n"
        f"8. Write 'done' to {outcome_file} if all steps succeeded.\n"
        f"   Write 'failed' to {outcome_file} if any step failed (include a brief\n"
        f"   error summary as the second line).\n\n"
        "IMPORTANT: Do not delete or modify any story files in workspace/stories/. "
        "Story state transitions are handled by the pipeline harness in Python."
    )


async def run(
    workspace_dir: Path,
    model: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
    effort: str = "medium",
) -> None:
    sentinels_dir = workspace_dir / ".sentinels"
    orchestrator_dir = sentinels_dir / "story-orchestrator"
    merge_queue_dir = sentinels_dir / "merge-queue"
    stories_dir = workspace_dir / "stories"
    pipeline_complete = sentinels_dir / "pipeline_complete"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_merger-agent"),
        allowed_tools=["Read", "Write", "Bash", "Glob"],
        permission_mode="acceptEdits",
        max_turns=100,
        model=model,
        effort=effort,
    )

    while True:
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        zip_path = get_next_merge_story(merge_queue_dir)
        if zip_path is None:
            print(f"[{agent_name}] Merge-queue empty — polling every {POLL_INTERVAL}s...")
            await anyio.sleep(POLL_INTERVAL)
            continue

        story_id = zip_path.stem  # STORY-NNN
        print(f"[{agent_name}] Merging {story_id} from {zip_path.name}...")

        # ── Python: unzip to staging area ─────────────────────────────────
        extract_dir = unzip_workspace_for_merge(zip_path, sentinels_dir)
        outcome_file = sentinels_dir / f"merge-{story_id}.outcome"
        outcome_file.unlink(missing_ok=True)

        # ── LLM: git branch, copy, commit, merge ──────────────────────────
        task = _build_task(story_id, extract_dir, workspace_dir, outcome_file)
        async for message in query(prompt=task, options=options):
            print_claude_message(agent_name, message)
            log_claude_message(conv_log_dir, agent_name, message, story_id)

        # ── Python: finalise based on LLM outcome ─────────────────────────
        outcome = outcome_file.read_text().strip() if outcome_file.exists() else ""
        if outcome.startswith("done"):
            mark_story_done_after_merge(stories_dir, story_id, run_log, agent_name, orchestrator_dir)
            zip_path.unlink(missing_ok=True)
            print(f"[{agent_name}] {story_id} merged successfully.")
        else:
            reason = outcome.split("\n", 1)[1].strip() if "\n" in outcome else "(no details)"
            print(f"[{agent_name}] WARNING: merge of {story_id} failed — {reason}")
            append_run_log(run_log, agent_name, f"merge failed: {story_id} — {reason}")

        # ── Cleanup staging area and outcome file ──────────────────────────
        shutil.rmtree(str(extract_dir), ignore_errors=True)
        if outcome_file.exists():
            outcome_file.unlink(missing_ok=True)


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir, args.effort)
