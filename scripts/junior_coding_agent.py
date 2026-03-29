"""Junior Coding Agent — claims and implements easy stories from stories/."""
import argparse
import re
import anyio
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

from token_logger import log_usage

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

POLL_INTERVAL = 60  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Junior Coding Agent (easy stories)")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "stories"),
        help="Directory containing story files (default: <project-root>/stories)",
    )
    parser.add_argument(
        "--workspace-dir",
        default=str(PROJECT_ROOT / "workspace"),
        help="Directory containing the workspace to implement stories in (default: <project-root>/workspace)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--token-log",
        default="",
        help="Path to JSONL file for token usage logging (optional)",
    )
    return parser.parse_args()


def _system_prompt() -> str:
    return (ROLES_DIR / "junior-coding-agent.md").read_text()


def _unclaimed_ready_stories(stories_dir: Path) -> list[Path]:
    """Return STORY-NNN.easy.ready.md files, sorted by story number."""
    return sorted(
        stories_dir.glob("STORY-*.easy.ready.md"),
        key=lambda p: p.name,
    )


async def _wait_for_ready_story(stories_dir: Path, pipeline_complete: Path) -> bool:
    """Poll until at least one unclaimed easy.ready story exists. Returns False on HALT/pipeline_complete."""
    halt_file = stories_dir / "HALT"
    last_status = ""
    while True:
        if halt_file.exists():
            print("[Junior Coding Agent] HALT detected while waiting — exiting.")
            return False

        if pipeline_complete.exists():
            print("[Junior Coding Agent] Pipeline complete sentinel detected — exiting.")
            return False

        if _unclaimed_ready_stories(stories_dir):
            return True

        status = "waiting for easy.ready stories"
        if status != last_status:
            print(
                f"[Junior Coding Agent] No ready easy stories available. "
                f"Polling every {POLL_INTERVAL}s..."
            )
            last_status = status

        await anyio.sleep(POLL_INTERVAL)


async def run(stories_dir: Path, workspace_dir: Path, model: str, token_log: Path | None) -> None:
    pipeline_complete = PROJECT_ROOT / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    if halt_file.exists():
        print("[Junior Coding Agent] HALT file detected on startup — exiting immediately.")
        return

    if not await _wait_for_ready_story(stories_dir, pipeline_complete):
        print("[Junior Coding Agent] No easy stories to process — exiting.")
        return

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Stories directory: {stories_dir}\n"
        f"Workspace directory: {workspace_dir}\n\n"
        "Begin the coding agent loop now:\n"
        f"1. Check for {halt_file} — exit immediately if it exists.\n"
        f"2. Scan {stories_dir} for files matching STORY-NNN.easy.ready.md. "
        "These have already been validated as ready to implement by the Story Orchestrator.\n"
        "3. Sort candidates by story number (ascending). Pick the lowest-numbered one.\n"
        "4. Atomically claim it by renaming STORY-NNN.easy.ready.md → STORY-NNN.easy.working.md. "
        "If the rename fails (race with another agent), try the next candidate. "
        "If none can be claimed, exit.\n"
        f"5. Read {workspace_dir}/CLAUDE.md for build, test, and lint instructions.\n"
        "6. Read the story file fully.\n"
        "7. Implement the story's acceptance criteria inside the workspace directory.\n"
        "8. Run tests and linter as instructed in CLAUDE.md.\n"
        f"9. Before committing, check for {halt_file} again — if found, perform the "
        "halt procedure (discard uncommitted changes, rename .easy.working.md back to "
        ".easy.ready.md, exit).\n"
        "10. On success: rename STORY-NNN.easy.working.md → STORY-NNN.easy.done.md, "
        "commit workspace changes, loop to step 1.\n"
        f"11. On failure: create {halt_file}, rename STORY-NNN.easy.working.md → "
        "STORY-NNN.easy.failed.md, perform halt procedure, exit."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=1000,
        model=model,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            log_usage(token_log, "junior", message.usage)
            print(f"\n\n[Junior Coding Agent finished — stop reason: {message.stop_reason}]")


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = Path(args.stories_dir)
    if not stories_dir.is_absolute():
        stories_dir = PROJECT_ROOT / stories_dir
    workspace_dir = Path(args.workspace_dir)
    if not workspace_dir.is_absolute():
        workspace_dir = PROJECT_ROOT / workspace_dir
    token_log = Path(args.token_log) if args.token_log else None
    anyio.run(run, stories_dir, workspace_dir, args.model, token_log)
