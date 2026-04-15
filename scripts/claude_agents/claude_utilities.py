"""Shared utilities for Claude agent implementations.

Provides:
  - build_common_arg_parser  — argparse parser pre-loaded with the five
                               arguments that every Claude agent accepts.
  - build_coding_task        — constructs the standard single-story task
                               prompt used by both Junior and Senior agents.
  - run_coding_story_loop    — the claim→copy→session→outcome→zip/finalise
                               polling loop shared by Junior and Senior agents.
"""
import argparse
import shutil
from pathlib import Path

import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import (
    append_run_log,
    claim_story,
    copy_workspace_for_story,
    finalise_story,
    get_story_id,
    load_role,
    zip_workspace_for_merge,
)
from conversation_logger import log_claude_message, print_claude_message

POLL_INTERVAL = 10  # seconds between polls when no work is available


def build_common_arg_parser(
    description: str,
    default_model: str,
    default_agent_name: str,
) -> argparse.ArgumentParser:
    """Return an ArgumentParser pre-loaded with the five common agent arguments.

    The caller may add agent-specific arguments before calling parse_args().

    Common arguments added:
      --workspace-dir   path to the shared workspace (default: "workspace")
      --model           Claude model identifier
      --run-log         path to run-log.jsonl (optional)
      --agent-name      name used in log output
      --conv-log-dir    directory for per-agent conversation JSONL logs (optional)
      --effort          Claude effort level: low / medium / high / max
    """
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    parser.add_argument(
        "--model",
        default=default_model,
        help=f"Claude model to use (default: {default_model})",
    )
    parser.add_argument(
        "--run-log",
        default="",
        help="Path to run-log.jsonl file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default=default_agent_name,
        help=f"Name used to identify this agent in logs (default: {default_agent_name})",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help=(
            "Directory for per-agent conversation JSONL logs; "
            "file named <agent-name>_log.jsonl (optional)"
        ),
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "max"],
        help="Claude effort level (default: medium)",
    )
    return parser


def build_coding_task(story_path: Path, workspace_dir: Path, outcome_file: Path) -> str:
    """Return the standard implementation task prompt for a single story.

    Used by both the Junior and Senior Coding Agents — the prompt text is
    identical for both; only the story path and options differ.
    """
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


async def run_coding_story_loop(
    workspace_dir: Path,
    model: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
    effort: str,
    role_name: str,
    story_patterns: list[str],
    no_stories_msg: str,
) -> None:
    """Polling loop shared by the Junior and Senior Coding Agents.

    Continuously claims stories matching *story_patterns*, runs an isolated
    LLM session inside a temp workspace copy, then either zips the result into
    the merge-queue (success) or calls finalise_story (failure/no-outcome).

    Args:
        workspace_dir:   path to the shared workspace.
        model:           Claude model identifier.
        run_log:         path to run-log.jsonl, or None.
        agent_name:      label used in console and log output.
        conv_log_dir:    directory for conversation JSONL logs, or None.
        effort:          Claude effort level string.
        role_name:       role file path passed to load_role(), e.g.
                         "claude_roles/claude_junior-coding-agent".
        story_patterns:  glob patterns passed to claim_story(), e.g.
                         ["STORY-*.easy.ready.md"].
        no_stories_msg:  message printed when no eligible story is available.
    """
    sentinels_dir = workspace_dir / ".sentinels"
    orchestrator_dir = sentinels_dir / "story-orchestrator"
    merge_queue_dir = sentinels_dir / "merge-queue"
    pipeline_complete = sentinels_dir / "pipeline_complete"

    base_options = dict(
        system_prompt=load_role(role_name),
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

        story_path = claim_story(orchestrator_dir, story_patterns)
        if story_path is None:
            print(f"[{agent_name}] {no_stories_msg} — polling every {POLL_INTERVAL}s...")
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

        options = ClaudeAgentOptions(cwd=str(temp_workspace), **base_options)
        task = build_coding_task(temp_story_path, temp_workspace, temp_outcome_file)

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
