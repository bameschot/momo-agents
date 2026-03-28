"""Story Reviewer Agent — triages .failed.md stories with the user and resets them."""
import argparse
import anyio
import sys
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

from token_logger import log_usage

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Story Reviewer Agent")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "stories"),
        help="Directory containing story files (default: <project-root>/stories)",
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
    return (ROLES_DIR / "story-reviewer.md").read_text()


async def run(stories_dir: Path, model: str, token_log: Path | None) -> None:
    halt_file = stories_dir / "HALT"
    failed_stories = sorted(stories_dir.glob("STORY-*.failed.md"))

    if not halt_file.exists():
        print("[Story Reviewer] No HALT file found — nothing to review.")
        return

    if not failed_stories:
        print("[Story Reviewer] HALT file exists but no .failed.md stories found.")
        print(f"  Removing stale HALT file: {halt_file}")
        halt_file.unlink()
        return

    print(f"[Story Reviewer] Found {len(failed_stories)} failed story(s) to review.")

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Stories directory: {stories_dir}\n"
        f"HALT file: {halt_file}\n"
        f"Failed stories: {', '.join(s.name for s in failed_stories)}\n\n"
        "Work through each failed story one at a time:\n"
        "1. Atomically claim the next .failed.md story by renaming it to .reviewing.md.\n"
        "2. Read the full story file including all accumulated failure notes.\n"
        "3. Use AskUserQuestion to present the user with:\n"
        "   - The story title, goal, and acceptance criteria.\n"
        "   - A plain-language summary of each failed attempt and what went wrong.\n"
        "   - Options: new approach, relaxed constraints, split the story, skip it.\n"
        "4. Based on the user's guidance, rewrite the entire story file content:\n"
        "   - Reset **Attempts** to 0.\n"
        "   - Preserve **Index** and **Depends on**.\n"
        "   - Rewrite context, acceptance criteria, and hints.\n"
        "   - Remove all old failure notes.\n"
        "5. Rename .reviewing.md → .md (story re-enters the pending queue).\n"
        "6. After ALL failed stories are resolved:\n"
        f"   - Delete {halt_file}.\n"
        "   - Report to the user that the pipeline is ready to resume."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["AskUserQuestion", "Read", "Write", "Glob", "Bash"],
        permission_mode="default",
        max_turns=500,
        model=model,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            log_usage(token_log, "reviewer", message.usage)
            print(f"\n\n[Story Reviewer Agent finished — stop reason: {message.stop_reason}]")

    # Confirm HALT was removed.
    if halt_file.exists():
        print(
            f"\nWarning: HALT file still exists at {halt_file}. "
            "The agent may not have resolved all failed stories.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = Path(args.stories_dir)
    if not stories_dir.is_absolute():
        stories_dir = PROJECT_ROOT / stories_dir
    token_log = Path(args.token_log) if args.token_log else None
    anyio.run(run, stories_dir, args.model, token_log)
