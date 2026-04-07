"""Story Reviewer Agent — triages .failed.md stories with the user and resets them."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, load_role, resolve_path
from conversation_logger import ConversationLogger
from token_logger import log_usage, print_message

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Story Reviewer Agent")
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "workspace" / "stories"),
        help="Directory containing story files (default: <project-root>/workspace/stories)",
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
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs; file named <agent-name>_log.jsonl (optional)",
    )
    return parser.parse_args()


async def run(stories_dir: Path, model: str, token_log: Path | None, conv_log_dir: Path | None) -> None:
    conv_logger = ConversationLogger.from_log_dir(conv_log_dir, "story-reviewer")
    halt_file = stories_dir / "HALT"
    # Glob matches STORY-NNN.[complexity].failed.md
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
        f"Project root: {stories_dir.parent}\n"
        f"Stories directory: {stories_dir}\n"
        f"HALT file: {halt_file}\n"
        f"Failed stories: {', '.join(s.name for s in failed_stories)}\n\n"
        "Story filenames follow the pattern STORY-NNN.[complexity].[state].md.\n\n"
        "Work through each failed story one at a time:\n"
        "1. Atomically claim the next .failed.md story by renaming it to .reviewing.md "
        "(preserve the complexity segment, e.g. STORY-001.easy.failed.md → STORY-001.easy.reviewing.md).\n"
        "2. Read the full story file including all accumulated failure notes.\n"
        "3. Use AskUserQuestion to present the user with:\n"
        "   - The story title, goal, and acceptance criteria.\n"
        "   - A plain-language summary of each failed attempt and what went wrong.\n"
        "   - Options: new approach, relaxed constraints, split the story, skip it.\n"
        "4. Based on the user's guidance, rewrite the entire story file content:\n"
        "   - Preserve **Index** and **Depends on**.\n"
        "   - Rewrite context, acceptance criteria, and hints.\n"
        "5. Rename STORY-NNN.[complexity].reviewing.md → STORY-NNN.md (bare, no complexity or state). "
        "This returns the story to the unprocessed queue so the Story Orchestrator "
        "re-evaluates it with the rewritten content.\n"
        "6. After ALL failed stories are resolved:\n"
        f"   - Delete {halt_file}.\n"
        "   - Report to the user that the pipeline is ready to resume."
    )

    options = ClaudeAgentOptions(
        cwd=str(stories_dir.parent),
        system_prompt=load_role("claude_roles/claude_story-reviewer"),
        allowed_tools=["AskUserQuestion", "Read", "Write", "Glob", "Bash"],
        permission_mode="default",
        max_turns=500,
        model=model,
    )

    async for message in query(prompt=task, options=options):
        log_usage(token_log, "reviewer", getattr(message, "usage", None), getattr(message, "total_cost_usd", None))
        print_message(message)
        conv_logger.log_claude_message(message, "review")

    if halt_file.exists():
        print(
            f"\nWarning: HALT file still exists at {halt_file}. "
            "The agent may not have resolved all failed stories.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    args = _parse_args()
    stories_dir = resolve_path(args.stories_dir)
    token_log = Path(args.token_log) if args.token_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, stories_dir, args.model, token_log, conv_log_dir)
