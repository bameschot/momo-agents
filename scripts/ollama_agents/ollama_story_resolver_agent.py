"""Ollama Story Resolver Agent — interactive triage of failed stories.

Scans for STORY-*.*.failed.md files, runs an agentic loop per story that uses
the ask_user tool to interact with the user, then resets resolved stories to
.ready.md so they can be picked up by a coding agent again.
"""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse

import anyio
from ollama import Message

from agent_utilities import append_run_log, load_role, resolve_path
from ollama_utilities import (
    DEFAULT_MODEL,
    DEFAULT_OLLAMA_HOST,
    RESOLVER_TOOLS,
    ToolExecutor,
    UserExitRequest,
    UserSkipRequest,
    add_ollama_args,
    make_client,
    run_agent_loop,
)

POLL_INTERVAL = 15  # seconds between scans when no failed stories exist
_FAILURE_REASONS_HEADING = "## Failure Reasons"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ollama Story Resolver Agent (failed story triage)")
    parser.add_argument(
        "--workspace-dir",
        default="workspace",
        help="Path to the workspace directory (default: workspace/ relative to project root)",
    )
    add_ollama_args(
        parser,
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-story-resolver",
    )
    return parser.parse_args()


def _find_failed_story(stories_dir: Path) -> Path | None:
    """Return the lowest-numbered failed story, or None if there are none."""
    candidates = sorted(stories_dir.glob("STORY-*.*.failed.md"), key=lambda p: p.name)
    return candidates[0] if candidates else None


def _strip_failure_reasons(story_path: Path) -> None:
    """Remove the '## Failure Reasons' section from story_path if present.

    Safety net in case the model forgot to strip it before writing the sentinel.
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
        f"1. Use `read_file` to read the story at {story_path} — "
        "focus on the '## Failure Reasons' section at the bottom.\n"
        "2. Use `ask_user` to present the failure reasons clearly to the user: "
        "what failed, what errors occurred, and what was attempted.\n"
        "3. Use `read_file`, `glob`, and `grep` to inspect relevant source files, "
        "tests, and CLAUDE.md for additional context as needed.\n"
        "4. Use `ask_user` to ask focused questions and understand the root cause.\n"
        "5. Use `ask_user` to propose a concrete resolution and get confirmation.\n"
        "6. Once the user confirms the resolution:\n"
        f"   a. Use `read_file` to read {story_path}, then use `write_file` to write "
        "it back with the '## Failure Reasons' section removed entirely and any "
        "agreed acceptance-criteria changes applied.\n"
        f"   b. Use `write_file` to write the word 'resolved' to {sentinel_file} "
        "— this must be the very last file-write tool call.\n"
        "7. Use `ask_user` to inform the user the story has been reset to ready.\n\n"
        "IMPORTANT: Use `ask_user` for all communication with the user. "
        "Do not write to the sentinel file until the user explicitly confirms resolution. "
        "Do not modify source code or test files."
    )


async def _run_resolver_session(
    story_path: Path,
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    agent_name: str,
    run_log: Path | None,
    conv_log_dir: Path | None,
) -> bool:
    """Run one resolver session for story_path via the Ollama agent loop.

    Returns True if the story was resolved and reset to .ready.md, False if
    the user skipped or the session ended without resolution.
    """
    story_id = story_path.name.split(".")[0]  # e.g. STORY-003
    sentinel_file = workspace_dir / ".sentinels" / f"{story_id}.resolver"
    sentinel_file.unlink(missing_ok=True)

    print(f"\n{'─' * 60}")
    print(f"[{agent_name}] Resolving: {story_path.name}")
    print(f"{'─' * 60}")
    print("During the session type 'skip' to move to the next story or 'exit' to stop.")
    print()

    executor = ToolExecutor(workspace_dir)
    client = make_client(ollama_host)
    system_prompt = load_role("ollama_roles/ollama-story-resolver")
    task = _build_task(story_path, workspace_dir, sentinel_file)
    messages: list[Message] = [Message(role="user", content=task)]

    try:
        await run_agent_loop(
            messages=messages,
            client=client,
            model=model,
            tools=RESOLVER_TOOLS,
            executor=executor,
            agent_name=agent_name,
            system_prompt=system_prompt,
            conv_log_dir=conv_log_dir,
            context=story_id,
        )
    except UserSkipRequest:
        print(f"\n[{agent_name}] Skipping {story_path.name}.")
        return False
    except UserExitRequest:
        print(f"\n[{agent_name}] Resolver stopped by user.")
        raise SystemExit(0)

    # Check whether the model wrote the sentinel — story is resolved.
    if sentinel_file.exists() and sentinel_file.read_text().strip() == "resolved":
        sentinel_file.unlink()

        # Safety net: strip Failure Reasons if the model left them in.
        _strip_failure_reasons(story_path)

        # Rename .failed.md → .ready.md (preserves complexity segment).
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

    print(f"[{agent_name}] Session ended without resolution — {story_path.name} stays failed.")
    return False


async def run(
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    orchestrator_dir = workspace_dir / ".sentinels" / "story-orchestrator"
    print(f"[{agent_name}] Story Resolver ready — scanning for failed stories every {POLL_INTERVAL}s.")
    print(f"[{agent_name}] Connected to Ollama at {ollama_host}, model={model}")
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
            ollama_host=ollama_host,
            agent_name=agent_name,
            run_log=run_log,
            conv_log_dir=conv_log_dir,
        )


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(
        run,
        workspace_dir,
        args.model,
        args.ollama_host,
        run_log,
        args.agent_name,
        conv_log_dir,
    )
