"""Junior Coding Agent — claims and implements easy stories one at a time."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path, wait_for_workspace
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


def _claim_story(stories_dir: Path) -> Path | None:
    """Atomically claim the lowest-numbered easy .ready story.

    Renames STORY-NNN.easy.ready.md → STORY-NNN.easy.working.md.
    Returns the working path on success, None if nothing could be claimed.
    """
    candidates = sorted(stories_dir.glob("STORY-*.easy.ready.md"), key=lambda p: p.name)
    for candidate in candidates:
        working = candidate.with_name(candidate.name.replace(".ready.md", ".working.md"))
        try:
            candidate.rename(working)
            return working
        except OSError:
            continue
    return None


def _build_task(story_path: Path, workspace_dir: Path, halt_file: Path) -> str:
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"HALT file: {halt_file}\n\n"
        "## Task\n"
        "1. Read workspace/CLAUDE.md — note build/test/lint commands and the Agent Exclusion List.\n"
        "2. Read the story file.\n"
        "3. Read the design doc(s) from the story's **Design ref** field "
        "(two paths separated by ' | ' — read whichever exist).\n"
        "4. Implement the acceptance criteria.\n"
        "5. Run tests and linter per CLAUDE.md.\n"
        f"6. Check {halt_file} — if found, perform the halt procedure.\n"
        "7. Success → rename .easy.working.md → .easy.done.md, commit.\n"
        f"8. Failure → create {halt_file}, rename .easy.working.md → "
        ".easy.failed.md, perform halt procedure."
    )


async def run(stories_dir: Path, workspace_dir: Path, model: str, run_log: Path | None, agent_name: str, conv_log_dir: Path | None) -> None:
    pipeline_complete = workspace_dir / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

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
        if halt_file.exists():
            print(f"[{agent_name}] HALT detected — exiting.")
            return
        if pipeline_complete.exists():
            print(f"[{agent_name}] Pipeline complete — exiting.")
            return

        story_path = _claim_story(stories_dir)
        if story_path is None:
            print(f"[{agent_name}] No easy.ready stories available — polling every {POLL_INTERVAL}s...")
            await anyio.sleep(POLL_INTERVAL)
            continue

        print(f"[{agent_name}] Claimed {story_path.name} — starting fresh session.")
        task = _build_task(story_path, workspace_dir, halt_file)
        story_context = story_path.stem.split(".")[0]  # e.g. STORY-001

        async for message in query(prompt=task, options=options):
            log_claude_message(conv_log_dir, agent_name, message, story_context)

        stem = story_path.name.replace(".working.md", "")
        done_path = story_path.with_name(stem + ".done.md")
        failed_path = story_path.with_name(stem + ".failed.md")
        if done_path.exists():
            append_run_log(run_log, agent_name, f"story done: {done_path.name}")
        elif failed_path.exists():
            append_run_log(run_log, agent_name, f"story failed: {failed_path.name}")


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, stories_dir, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir)
