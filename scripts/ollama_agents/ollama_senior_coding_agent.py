"""Ollama Senior Coding Agent — claims and implements medium/hard stories one at a time.

Each story is worked on inside an isolated copy of the workspace so that
parallel agents never interfere with each other's file trees.  When the LLM
reports success the temp workspace is zipped into the merge-queue; the Merger
Agent then commits and merges the changes in story order.  Failed or reset
stories are handled the same as before (finalise_story handles the rename).
"""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import anyio

from agent_utilities import resolve_path
from ollama_utilities import (
    DEFAULT_MODEL,
    build_ollama_arg_parser,
    run_ollama_coding_story_loop,
)

POLL_INTERVAL = 10  # seconds between polls when no eligible story is available


def _parse_args():
    parser = build_ollama_arg_parser(
        description="Ollama Senior Coding Agent (medium and hard stories)",
        default_model=DEFAULT_MODEL,
        default_agent_name="ollama-senior-coding-agent",
    )
    return parser.parse_args()


async def run(
    workspace_dir: Path,
    model: str,
    ollama_host: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
) -> None:
    await run_ollama_coding_story_loop(
        workspace_dir=workspace_dir,
        model=model,
        ollama_host=ollama_host,
        run_log=run_log,
        agent_name=agent_name,
        conv_log_dir=conv_log_dir,
        role_name="ollama_roles/ollama-senior-coding-agent",
        story_patterns=["STORY-*.medium.ready.md", "STORY-*.hard.ready.md"],
        no_stories_msg="No medium/hard.ready stories available",
        poll_interval=POLL_INTERVAL,
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
