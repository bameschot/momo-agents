"""Business Analyst Agent — reads a design document and writes story files."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory (agent_utilities, token_logger).
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path, wait_for_workspace
from token_logger import log_usage, print_message

DEFAULT_MODEL = "claude-sonnet-4-6"

POLL_INTERVAL = 10  # seconds between polls while waiting for workspace/CLAUDE.md


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Business Analyst Agent")
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. design/my-feature.md)",
    )
    parser.add_argument(
        "--stories-dir",
        default="",
        help="Directory where story files are written (default: <workspace-dir>/stories)",
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
        default="business-analyst",
        help="Name used to identify this agent in logs (default: business-analyst)",
    )
    return parser.parse_args()


async def run(design_path: Path, stories_dir: Path, workspace_dir: Path, model: str, tokens_log_dir: Path | None, run_log: Path | None, agent_name: str) -> None:
    token_log = tokens_log_dir / f"{agent_name}.jsonl" if tokens_log_dir else None
    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    await wait_for_workspace(workspace_dir, "Business Analyst Agent", POLL_INTERVAL)

    stories_dir.mkdir(parents=True, exist_ok=True)

    next_index = len(list(stories_dir.glob("STORY-*.md"))) + 1

    task = (
        f"Project root: {workspace_dir}\n"
        f"Design document: {design_path}\n"
        f"Stories output directory: {stories_dir}\n"
        f"Next story number to use: {next_index:03d} (zero-padded three digits)\n\n"
        "Read the design document in full. Decompose it into an ordered set of discrete, "
        "implementable stories and write each one to the stories directory as STORY-NNN.md. "
        "Follow the story file format defined in your role exactly.\n\n"
        "Complexity rules (mandatory):\n"
        "- Assign every story a complexity of easy, medium, or hard.\n"
        "- Include the complexity label in both the heading and the **Complexity** field.\n"
        "- Strongly prefer easy (~3 hours) and medium (~6 hours) stories. Split any hard story into smaller pieces "
        "unless doing so would make the resulting stories incoherent or non-implementable on their own.\n\n"
        "Do not leave open questions — resolve ambiguities from the design before writing."
    )

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_business-analyst"),
        allowed_tools=["Read", "Write", "Glob"],
        permission_mode="acceptEdits",
        max_turns=200,
        model=model,
    )

    before = set(stories_dir.glob("STORY-*.md"))

    async for message in query(prompt=task, options=options):
        log_usage(token_log, "ba", getattr(message, "usage", None), getattr(message, "total_cost_usd", None))
        print_message(message)

    after = set(stories_dir.glob("STORY-*.md"))
    for story_file in sorted(after - before, key=lambda p: p.name):
        append_run_log(run_log, agent_name, f"story created: {story_file.name}")


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    tokens_log_dir = Path(args.tokens_log_dir) if args.tokens_log_dir else None
    run_log = Path(args.run_log) if args.run_log else None
    anyio.run(run, design_path, stories_dir, workspace_dir, args.model, tokens_log_dir, run_log, args.agent_name)
