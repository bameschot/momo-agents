"""Business Analyst Agent — reads a design document and writes story files."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path, wait_for_workspace
from conversation_logger import log_claude_message

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
        "--run-log",
        default="",
        help="Path to run-log.json file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default="business-analyst",
        help="Name used to identify this agent in logs (default: business-analyst)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs; file named <agent-name>_log.jsonl (optional)",
    )
    return parser.parse_args()


def _design_stem(design_path: Path) -> str:
    """Return a git-safe stem derived from the design file name."""
    name = design_path.name
    for suffix in (".new.md", ".processed.md", ".md"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
            break
    return name


async def run(design_path: Path, stories_dir: Path, workspace_dir: Path, model: str, run_log: Path | None, agent_name: str, conv_log_dir: Path | None) -> None:
    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    await wait_for_workspace(workspace_dir, "Business Analyst Agent", POLL_INTERVAL)

    stories_dir.mkdir(parents=True, exist_ok=True)

    next_index = len(list(stories_dir.glob("STORY-*.md"))) + 1
    branch_name = f"ba/{_design_stem(design_path)}"

    task = (
        f"Project root: {workspace_dir}\n"
        f"Design document: {design_path}\n"
        f"Stories output directory: {stories_dir}\n"
        f"Next story number to use: {next_index:03d} (zero-padded three digits)\n\n"
        "Read the design document in full. Decompose it into an ordered set of discrete, "
        "implementable stories and write each one to the stories directory as STORY-NNN.md. "
        "Follow the story file format and all rules defined in your role exactly.\n\n"
        "Follow this git workflow exactly:\n"
        f"1. Before writing any stories, capture the current branch name with: git branch --show-current\n"
        f"2. Create and switch to a new branch: git checkout -b {branch_name}\n"
        "3. Write ALL story files to the stories directory. Do NOT commit between stories.\n"
        "4. After all stories are written, stage and commit them in a single commit:\n"
        f"   git add {stories_dir} && git commit -m 'add stories for {_design_stem(design_path)}'\n"
        "5. Merge the story branch back into the original branch:\n"
        f"   git checkout <original-branch> && git merge {branch_name}\n"
        "(Replace <original-branch> with the branch name captured in step 1.)"
    )

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_business-analyst"),
        allowed_tools=["Read", "Write", "Glob", "Bash"],
        permission_mode="acceptEdits",
        max_turns=200,
        model=model,
    )

    before = set(stories_dir.glob("STORY-*.md"))

    async for message in query(prompt=task, options=options):
        log_claude_message(conv_log_dir, agent_name, message, "business-analysis")

    after = set(stories_dir.glob("STORY-*.md"))
    for story_file in sorted(after - before, key=lambda p: p.name):
        append_run_log(run_log, agent_name, f"story created: {story_file.name}")

    if design_path.name.endswith(".new.md"):
        processed_path = design_path.with_name(design_path.name.replace(".new.md", ".processed.md"))
        design_path.rename(processed_path)
        print(f"[{agent_name}] Design marked as processed: {processed_path.name}", flush=True)
        append_run_log(run_log, agent_name, f"design processed: {processed_path.name}")


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    stories_dir = resolve_path(args.stories_dir) if args.stories_dir else workspace_dir / "stories"
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, design_path, stories_dir, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir)
