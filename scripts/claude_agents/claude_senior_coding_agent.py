"""Senior Coding Agent — claims medium/hard stories one at a time.

Each story is worked on inside an isolated copy of the workspace so that
parallel agents never interfere with each other's file trees.  When the LLM
reports success the temp workspace is zipped into the merge-queue; the Merger
Agent then commits and merges the changes in story order.  Failed or reset
stories are handled the same as before (finalise_story handles the rename).
"""
import shutil
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import (
    append_run_log,
    claim_story,
    copy_workspace_for_story,
    finalise_story,
    get_story_id,
    load_role,
    resolve_path,
    wait_for_workspace,
    zip_workspace_for_merge,
)
from conversation_logger import log_claude_message, print_claude_message

POLL_INTERVAL = 10  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Senior Coding Agent (medium and hard stories)")
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
        help="Path to run-log.json file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default="senior-coding-agent",
        help="Name used to identify this agent in logs (default: senior-coding-agent)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs; file named <agent-name>_log.jsonl (optional)",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "max"],
        help="Claude effort level (default: medium)",
    )
    return parser.parse_args()


def _build_task(story_path: Path, workspace_dir: Path, outcome_file: Path) -> str:
    """Build a focused single-story task prompt."""
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"Outcome file: {outcome_file}\n\n"
        "## Task\n"
        f"1. Read {workspace_dir}/CLAUDE.md — note build/test/lint commands and the Agent Exclusion List.\n"
        "2. Read the story file.\n"
        "3. Read the design doc(s) from the story's **Design ref** field "
        "(two paths separated by ' | ' — read whichever exist).\n"
        "4. Implement the acceptance criteria.\n"
        "5. Run tests and linter per CLAUDE.md.\n"
        f"6. Success → write the word 'done' to {outcome_file}.\n"
        f"7. Failure:\n"
        f"   a. Read the story file at {story_path}, then use Edit to append a "
        f"'## Failure Reasons' section at the very end of the file. "
        f"Include a concise description of what went wrong: which tests or lint checks failed, "
        f"relevant error messages, and what was attempted.\n"
        f"   b. Write the word 'failed' to {outcome_file}.\n\n"
        "IMPORTANT: Never rename, delete, or change the file extension of story files "
        "(.ready.md / .working.md / .done.md / .failed.md) — "
        "story file state transitions are managed by the pipeline harness outside the LLM session. "
        "The only permitted edit to a story file is appending a '## Failure Reasons' section when a story fails."
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
    pipeline_complete = sentinels_dir / "pipeline_complete"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    base_options = dict(
        system_prompt=load_role("claude_roles/claude_senior-coding-agent"),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=300,
        model=model,
        effort=effort,
    )

    while True:
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        story_path = claim_story(orchestrator_dir, ["STORY-*.medium.ready.md", "STORY-*.hard.ready.md"])
        if story_path is None:
            print(f"[{agent_name}] No medium/hard.ready stories available — polling every {POLL_INTERVAL}s...")
            await anyio.sleep(POLL_INTERVAL)
            continue

        story_id = get_story_id(story_path)
        print(f"[{agent_name}] Claimed {story_path.name} — copying workspace to temp/{story_id}...")

        # ── Isolate: copy workspace into a temp directory ──────────────────
        temp_workspace = copy_workspace_for_story(workspace_dir, sentinels_dir, story_id)
        temp_story_path = temp_workspace / "stories" / story_path.name
        # The orchestrator dir is excluded from the workspace copy; place the
        # story file explicitly so the LLM can read it at the expected path.
        shutil.copy2(str(story_path), str(temp_story_path))
        temp_outcome_file = sentinels_dir / f"{story_id}.outcome"

        print(f"[{agent_name}] Starting session in isolated workspace {temp_workspace}...")

        options = ClaudeAgentOptions(
            cwd=str(temp_workspace),
            **base_options,
        )
        task = _build_task(temp_story_path, temp_workspace, temp_outcome_file)

        async for message in query(prompt=task, options=options):
            print_claude_message(agent_name, message)
            log_claude_message(conv_log_dir, agent_name, message, story_id)

        # ── Post-session: dispatch based on outcome ────────────────────────
        outcome = temp_outcome_file.read_text().strip() if temp_outcome_file.exists() else ""

        if outcome == "done":
            # Zip temp workspace → merge-queue; leave main story as .working
            zip_workspace_for_merge(temp_workspace, story_id, merge_queue_dir)
            append_run_log(run_log, agent_name, f"story queued for merge: {story_id}")
            print(f"[{agent_name}] {story_id} done — queued for merge.")
            temp_outcome_file.unlink(missing_ok=True)
        else:
            # For failed / no-outcome: copy updated story file back to the orchestrator dir
            # so failure reasons written by the LLM are preserved, then finalise.
            if temp_story_path.exists():
                shutil.copy2(str(temp_story_path), str(story_path))
            finalise_story(story_path, temp_outcome_file, run_log, agent_name)

        # ── Cleanup temp workspace ─────────────────────────────────────────
        shutil.rmtree(str(temp_workspace), ignore_errors=True)


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir, args.effort)
