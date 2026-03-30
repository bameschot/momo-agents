"""Junior Coding Agent — claims and implements easy stories from stories/."""
import argparse
import re
import anyio
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from token_logger import log_usage, print_message

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

POLL_INTERVAL = 60  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Junior Coding Agent (easy stories)")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "workspace" / "stories"),
        help="Directory containing story files (default: <project-root>/workspace/stories)",
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


async def _wait_for_workspace(workspace_dir: Path) -> None:
    """Block until workspace_dir/CLAUDE.md exists (scaffolding agent has finished)."""
    claude_md = workspace_dir / "CLAUDE.md"
    if claude_md.exists():
        return
    print(
        f"[Junior Coding Agent] Waiting for scaffolding to complete "
        f"({claude_md}) — polling every {POLL_INTERVAL}s..."
    )
    while not claude_md.exists():
        await anyio.sleep(POLL_INTERVAL)
    print("[Junior Coding Agent] Workspace ready — proceeding.")


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

    await _wait_for_workspace(workspace_dir)

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
        "## Startup (do this once before the loop)\n"
        f"1. Read {workspace_dir}/CLAUDE.md and retain its build, test, and lint "
        "instructions for the entire session. Do not re-read it on each story.\n"
        f"2. Based on the tech stack described in {workspace_dir}/CLAUDE.md, determine which "
        f"folders in {workspace_dir}/ are generated, vendored, or tooling artefacts "
        "(e.g. dependency caches, build output, virtual environments, compiler artefacts, "
        "tool caches). Retain this exclusion list and avoid reading from those folders during "
        "the session.\n\n"
        "## Coding loop\n"
        f"3. Check for {halt_file} — exit immediately if it exists.\n"
        f"4. Scan {stories_dir} for files matching STORY-NNN.easy.ready.md. "
        "These have already been validated as ready to implement by the Story Orchestrator.\n"
        "5. Sort candidates by story number (ascending). Pick the lowest-numbered one.\n"
        "6. Atomically claim it by renaming STORY-NNN.easy.ready.md → STORY-NNN.easy.working.md. "
        "If the rename fails (race with another agent), try the next candidate. "
        "If none can be claimed, exit.\n"
        "7. Read the story file fully.\n"
        "8. Implement the story's acceptance criteria inside the workspace directory. "
        "Do not read from the technical folders identified in step 2.\n"
        "9. Run tests and linter using the instructions you retained from CLAUDE.md on startup.\n"
        f"10. Before committing, check for {halt_file} again — if found, perform the "
        "halt procedure (discard uncommitted changes, rename .easy.working.md back to "
        ".easy.ready.md, exit).\n"
        "11. On success: rename STORY-NNN.easy.working.md → STORY-NNN.easy.done.md, "
        "commit workspace changes, loop to step 3.\n"
        f"12. On failure: create {halt_file}, rename STORY-NNN.easy.working.md → "
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
        log_usage(token_log, "junior", getattr(message, "usage", None), getattr(message, "total_cost_usd", None))
        print_message(message)


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
