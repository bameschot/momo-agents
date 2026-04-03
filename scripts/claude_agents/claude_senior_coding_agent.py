"""Senior Coding Agent — claims medium/hard stories one at a time; starts a fresh query per story."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path, wait_for_workspace
from token_logger import log_usage, print_message

POLL_INTERVAL = 60  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Senior Coding Agent (medium and hard stories)")
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
        "--tokens-log-dir",
        default="",
        help="Directory for token usage JSONL logs; file is named <agent-name>.jsonl (optional)",
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
    return parser.parse_args()


def _claim_story(stories_dir: Path) -> Path | None:
    """Atomically claim the lowest-numbered medium or hard .ready story.

    Renames STORY-NNN.[complexity].ready.md → STORY-NNN.[complexity].working.md.
    Returns the working path on success, None if nothing could be claimed.
    """
    medium = list(stories_dir.glob("STORY-*.medium.ready.md"))
    hard = list(stories_dir.glob("STORY-*.hard.ready.md"))
    candidates = sorted(medium + hard, key=lambda p: p.name)
    for candidate in candidates:
        working = candidate.with_name(candidate.name.replace(".ready.md", ".working.md"))
        try:
            candidate.rename(working)
            return working
        except OSError:
            continue
    return None


def _build_task(story_path: Path, workspace_dir: Path, claude_md: str, halt_file: Path) -> str:
    """Build a focused single-story task prompt."""
    return (
        f"Story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"HALT file: {halt_file}\n\n"
        f"## workspace/CLAUDE.md\n\n{claude_md}\n\n"
        "## Task\n"
        "1. Read the story file.\n"
        "2. Read the design doc(s) from the story's **Design ref** field "
        "(two paths separated by ' | ' — read whichever exist).\n"
        "3. Note the '## Agent Exclusion List' in CLAUDE.md above — never read from or "
        "write to those paths.\n"
        "4. Implement the acceptance criteria.\n"
        "5. Run tests and linter per CLAUDE.md.\n"
        f"6. Check {halt_file} — if found, perform the halt procedure.\n"
        "7. Success → rename .[complexity].working.md → .[complexity].done.md, commit.\n"
        f"8. Failure → create {halt_file}, rename .[complexity].working.md → "
        ".[complexity].failed.md, perform halt procedure."
    )


async def run(stories_dir: Path, workspace_dir: Path, model: str, tokens_log_dir: Path | None, run_log: Path | None, agent_name: str) -> None:
    token_log = tokens_log_dir / f"{agent_name}.jsonl" if tokens_log_dir else None
    pipeline_complete = workspace_dir / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)

    # Read workspace/CLAUDE.md once for the lifetime of this process.
    claude_md = (workspace_dir / "CLAUDE.md").read_text()

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("senior-coding-agent"),
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
            print(f"[{agent_name}] No medium/hard.ready stories available — polling every {POLL_INTERVAL}s...")
            await anyio.sleep(POLL_INTERVAL)
            continue

        print(f"[{agent_name}] Claimed {story_path.name} — starting fresh session.")
        task = _build_task(story_path, workspace_dir, claude_md, halt_file)

        async for message in query(prompt=task, options=options):
            log_usage(token_log, "senior", getattr(message, "usage", None), getattr(message, "total_cost_usd", None))
            print_message(message)

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
    tokens_log_dir = Path(args.tokens_log_dir) if args.tokens_log_dir else None
    run_log = Path(args.run_log) if args.run_log else None
    anyio.run(run, stories_dir, workspace_dir, args.model, tokens_log_dir, run_log, args.agent_name)
