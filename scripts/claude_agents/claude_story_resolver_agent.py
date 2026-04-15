"""Story Resolver Agent — interactive triage of failed stories.

Scans for STORY-*.*.failed.md files, opens an interactive Claude session per
story to help the user diagnose and resolve the failure, then resets the story
to .ready.md so it can be picked up by a coding agent again.
"""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ThinkingBlock,
)

from agent_utilities import append_run_log, load_role, resolve_path
from conversation_logger import log_claude_message

POLL_INTERVAL = 15  # seconds between scans when no failed stories exist
DEFAULT_MODEL = "claude-sonnet-4-6"
_FAILURE_REASONS_HEADING = "## Failure Reasons"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Story Resolver Agent (failed story triage)")
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
        help="Path to run-log.jsonl file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default="story-resolver",
        help="Name used to identify this agent in logs (default: story-resolver)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs (optional)",
    )
    parser.add_argument(
        "--effort",
        default="medium",
        choices=["low", "medium", "high", "max"],
        help="Claude effort level (default: medium)",
    )
    return parser.parse_args()


def _find_failed_story(stories_dir: Path) -> Path | None:
    """Return the lowest-numbered failed story, or None if there are none."""
    candidates = sorted(stories_dir.glob("STORY-*.*.failed.md"), key=lambda p: p.name)
    return candidates[0] if candidates else None


def _strip_failure_reasons(story_path: Path) -> None:
    """Remove the '## Failure Reasons' section from story_path if present.

    Called as a safety net in case Claude forgot to strip it before writing
    the sentinel.  The section runs from its heading to the end of file.
    """
    content = story_path.read_text()
    if _FAILURE_REASONS_HEADING not in content:
        return
    idx = content.index(_FAILURE_REASONS_HEADING)
    stripped = content[:idx].rstrip() + "\n"
    story_path.write_text(stripped)


def _build_task(story_path: Path, workspace_dir: Path, sentinel_file: Path) -> str:
    return (
        f"Failed story: {story_path}\n"
        f"Workspace: {workspace_dir}\n"
        f"Sentinel file: {sentinel_file}\n\n"
        "## Task\n"
        f"1. Read the story file at {story_path} — focus on the "
        "'## Failure Reasons' section at the bottom.\n"
        "2. Present the failure reasons to the user clearly and concisely: "
        "what failed, what errors occurred, and what was attempted.\n"
        "3. Ask focused questions to understand the root cause. "
        "Use Read, Glob, and Grep to inspect workspace source files, tests, "
        "and CLAUDE.md for additional context as needed.\n"
        "4. Propose concrete solutions and discuss them with the user until "
        "a resolution strategy is agreed.\n"
        "5. When the user asks you to 'update the story':\n"
        f"   a. Edit {story_path} to remove the '## Failure Reasons' section "
        "entirely (from the heading to the end of file).\n"
        "   b. Apply any agreed changes to the story's acceptance criteria "
        "or other sections (e.g. clarifying a requirement, fixing a wrong "
        "assumption, adjusting scope).\n"
        f"   c. As the very last step, write the word 'resolved' to {sentinel_file}.\n\n"
        "IMPORTANT: Do not write to the sentinel file until the user explicitly "
        "asks you to update the story. Do not modify source code or test files — "
        "only fix the story definition itself."
    )


async def _stream_response(
    client: ClaudeSDKClient,
    conv_log_dir: Path | None,
    agent_name: str,
    context: str,
) -> tuple[str | None, dict | None]:
    """Stream and print the agent response. Returns (stop_reason, usage)."""
    stop_reason = None
    usage = None
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ThinkingBlock) and block.thinking:
                    print(f"[{agent_name}][thinking] {block.thinking}", flush=True)
                elif isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            stop_reason = message.stop_reason
            usage = message.usage
        log_claude_message(conv_log_dir, agent_name, message, context)
    return stop_reason, usage


async def _run_resolver_session(
    story_path: Path,
    workspace_dir: Path,
    model: str,
    agent_name: str,
    run_log: Path | None,
    conv_log_dir: Path | None,
) -> bool:
    """Run one interactive resolver session for story_path.

    Returns True if the story was successfully resolved and reset to .ready.md,
    False if the user skipped or the session ended without resolution.
    """
    story_id = story_path.name.split(".")[0]  # e.g. STORY-003
    sentinel_file = workspace_dir / ".sentinels" / f"{story_id}.resolver"
    sentinel_file.unlink(missing_ok=True)

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_story-resolver"),
        allowed_tools=["Read", "Write", "Edit", "Glob", "Grep"],
        permission_mode="acceptEdits",
        max_turns=100,
        model=model,
        effort=effort,
    )

    task = _build_task(story_path, workspace_dir, sentinel_file)

    print(f"\n{'─' * 60}")
    print(f"[{agent_name}] Resolving: {story_path.name}")
    print(f"{'─' * 60}")
    print("Type 'skip' to move to the next failed story.")
    print("Type 'exit' to stop the resolver.")
    print()

    async with ClaudeSDKClient(options=options) as client:
        await client.query(task)
        await _stream_response(client, conv_log_dir, agent_name, story_id)
        print()

        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print(f"\n[{agent_name}] Session interrupted.")
                return False

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit"):
                print(f"[{agent_name}] Resolver stopped by user.")
                raise SystemExit(0)

            if user_input.lower() == "skip":
                print(f"[{agent_name}] Skipping {story_path.name}.")
                return False

            await client.query(user_input)
            await _stream_response(client, conv_log_dir, agent_name, story_id)
            print()

            # Check whether Claude wrote the sentinel — story is resolved.
            if sentinel_file.exists() and sentinel_file.read_text().strip() == "resolved":
                sentinel_file.unlink()

                # Safety net: strip Failure Reasons if Claude left them in.
                _strip_failure_reasons(story_path)

                # Rename .failed.md → .ready.md  (preserves complexity segment)
                ready_name = story_path.name.replace(".failed.md", ".ready.md")
                ready_path = story_path.with_name(ready_name)
                story_path.rename(ready_path)

                print(f"\n[{agent_name}] Story reset to ready: {ready_path.name}")
                append_run_log(
                    run_log,
                    agent_name,
                    f"story reset to ready after resolution: {ready_path.name}",
                )
                return True

    return False


async def run(
    workspace_dir: Path,
    model: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
    effort: str = "medium",
) -> None:
    orchestrator_dir = workspace_dir / ".sentinels" / "story-orchestrator"
    print(f"[{agent_name}] Story Resolver ready — scanning for failed stories every {POLL_INTERVAL}s.")
    print("When a failed story is found you will be prompted to resolve it interactively.")
    print()

    while True:
        story_path = _find_failed_story(orchestrator_dir)

        if story_path is None:
            print(f"[{agent_name}] No failed stories — polling every {POLL_INTERVAL}s...", flush=True)
            await anyio.sleep(POLL_INTERVAL)
            continue

        await _run_resolver_session(
            story_path=story_path,
            workspace_dir=workspace_dir,
            model=model,
            agent_name=agent_name,
            run_log=run_log,
            conv_log_dir=conv_log_dir,
        )


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir, args.effort)
