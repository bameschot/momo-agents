"""Junior Coding Agent — claims and implements easy stories one at a time.

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

from agent_utilities import resolve_path, wait_for_workspace
from claude_utilities import POLL_INTERVAL, build_common_arg_parser, run_coding_story_loop

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args():
    parser = build_common_arg_parser(
        description="Junior Coding Agent (easy stories)",
        default_model=DEFAULT_MODEL,
        default_agent_name="junior-coding-agent",
    )
    return parser.parse_args()


async def run(
    workspace_dir: Path,
    model: str,
    run_log: Path | None,
    agent_name: str,
    conv_log_dir: Path | None,
    effort: str = "medium",
) -> None:
    await wait_for_workspace(workspace_dir, agent_name, POLL_INTERVAL)
    await run_coding_story_loop(
        workspace_dir=workspace_dir,
        model=model,
        run_log=run_log,
        agent_name=agent_name,
        conv_log_dir=conv_log_dir,
        effort=effort,
        role_name="claude_roles/claude_junior-coding-agent",
        story_patterns=["STORY-*.easy.ready.md"],
        no_stories_msg="No easy.ready stories available",
    )


if __name__ == "__main__":
    args = _parse_args()
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir, args.effort)
