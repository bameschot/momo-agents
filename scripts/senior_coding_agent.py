"""Senior Coding Agent — claims medium/hard stories one at a time; starts a fresh query per story."""
import argparse
import anyio
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

from token_logger import log_usage, print_message

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

POLL_INTERVAL = 60  # seconds between polls when no eligible story is available

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Senior Coding Agent (medium and hard stories)")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "stories"),
        help="Directory containing story files (default: <project-root>/stories)",
    )
    parser.add_argument(
        "--workspace-dir",
        default=str(PROJECT_ROOT / "workspace"),
        help="Workspace directory (default: <project-root>/workspace)",
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
    return (ROLES_DIR / "senior-coding-agent.md").read_text()


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


async def _wait_for_workspace(workspace_dir: Path) -> None:
    """Block until workspace_dir/CLAUDE.md exists (scaffolding agent has finished)."""
    claude_md = workspace_dir / "CLAUDE.md"
    if claude_md.exists():
        return
    print(
        f"[Senior Coding Agent] Waiting for scaffolding to complete "
        f"({claude_md}) — polling every {POLL_INTERVAL}s..."
    )
    while not claude_md.exists():
        await anyio.sleep(POLL_INTERVAL)
    print("[Senior Coding Agent] Workspace ready — proceeding.")


def _build_task(story_path: Path, workspace_dir: Path, claude_md: str, halt_file: Path) -> str:
    """Build a focused single-story task prompt."""
    return (
        f"Story file: {story_path}\n"
        f"Workspace directory: {workspace_dir}\n\n"
        f"## workspace/CLAUDE.md\n\n{claude_md}\n\n"
        "## Your task\n\n"
        "1. Read the story file fully.\n"
        "2. Based on the tech stack described in workspace/CLAUDE.md above, identify which "
        f"folders in {workspace_dir}/ are generated, vendored, or tooling artefacts "
        "(e.g. dependency caches, build output, virtual environments, compiler artefacts, "
        "tool caches). Avoid reading from those folders.\n"
        "3. Implement the story's acceptance criteria inside the workspace directory.\n"
        "4. Run tests and linter as instructed in workspace/CLAUDE.md above.\n"
        f"5. Before committing, check for {halt_file} — if found, perform the halt procedure.\n"
        "6. On success: rename the story file from .[complexity].working.md → "
        ".[complexity].done.md, then commit all workspace changes with a clear message "
        "referencing the story.\n"
        f"7. On failure: create {halt_file} (empty file), rename the story file from "
        ".[complexity].working.md → .[complexity].failed.md, then perform the halt procedure."
    )


async def run(stories_dir: Path, workspace_dir: Path, model: str, token_log: Path | None) -> None:
    pipeline_complete = PROJECT_ROOT / ".sentinels" / "pipeline_complete"
    halt_file = stories_dir / "HALT"

    await _wait_for_workspace(workspace_dir)

    # Read workspace/CLAUDE.md once for the lifetime of this process.
    claude_md = (workspace_dir / "CLAUDE.md").read_text()

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=300,
        model=model,
    )

    while True:
        if halt_file.exists():
            print("[Senior Coding Agent] HALT detected — exiting.")
            return
        if pipeline_complete.exists():
            print("[Senior Coding Agent] Pipeline complete — exiting.")
            return

        story_path = _claim_story(stories_dir)
        if story_path is None:
            print(
                f"[Senior Coding Agent] No medium/hard.ready stories available — "
                f"polling every {POLL_INTERVAL}s..."
            )
            await anyio.sleep(POLL_INTERVAL)
            continue

        print(f"[Senior Coding Agent] Claimed {story_path.name} — starting fresh session.")
        task = _build_task(story_path, workspace_dir, claude_md, halt_file)

        async for message in query(prompt=task, cwd=workspace_dir, options=options):
            log_usage(token_log, "senior", getattr(message, "usage", None), getattr(message, "total_cost_usd", None))
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
