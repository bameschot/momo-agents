"""Junior Coding Agent — claims and implements easy stories one at a time."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import claim_story, finalise_story, load_role, resolve_path, wait_for_workspace
from conversation_logger import log_claude_message

POLL_INTERVAL = 10  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Junior Coding Agent (easy stories)")
    parser.add_argument(
        "--stories-dir",
        default="",
        help="Directory containing story files (default: <workspace-dir>/stories)",
    )
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
        default="junior-coding-agent",
        help="Name used to identify this agent in logs (default: junior-coding-agent)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs; file named <agent-name>_log.jsonl (optional)",
    )
    return parser.parse_args()



def _build_task(story_path: Path, workspace_dir: Path, outcome_file: Path) -> str:
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"Outcome file: {outcome_file}\n\n"
        "## Task\n"
        "1. Read workspace/CLAUDE.md — note build/test/lint commands and the Agent Exclusion List.\n"
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



async def run(stories_dir: Path, workspace_dir: Path, model: str, run_log: Path | None, agent_name: str, conv_log_dir: Path | None) -> None:
    pipeline_complete = workspace_dir / ".sentinels" / "pipeline_complete"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_junior-coding-agent"),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=300,
        model=model,
    )

    while True:
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        story_path = claim_story(stories_dir, ["STORY-*.easy.ready.md"])
        if story_path is None:
            print(f"[{agent_name}] No easy.ready stories available — polling every {POLL_INTERVAL}s...")
            await anyio.sleep(POLL_INTERVAL)
            continue

        print(f"[{agent_name}] Claimed {story_path.name} — starting fresh session.")
        story_id = story_path.stem.split(".")[0]  # e.g. STORY-001
        outcome_file = workspace_dir / ".sentinels" / f"{story_id}.outcome"
        task = _build_task(story_path, workspace_dir, outcome_file)

        async for message in query(prompt=task, options=options):
            log_claude_message(conv_log_dir, agent_name, message, story_id)

        finalise_story(story_path, outcome_file, run_log, agent_name)


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, stories_dir, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir)
