"""Project Initialiser Agent — scaffolds workspace/ from a design document."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path
from conversation_logger import log_claude_message

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project Initialiser Agent")
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. design/my-feature.md)",
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
        default="project-initialiser",
        help="Name used to identify this agent in logs (default: project-initialiser)",
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


async def run(design_path: Path, workspace_dir: Path, model: str, run_log: Path | None, agent_name: str, conv_log_dir: Path | None) -> None:
    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    stem = _design_stem(design_path)
    branch_name = f"pi/{stem}"

    task = (
        f"Workspace: {workspace_dir}\n"
        f"Design document: {design_path}\n\n"
        "Read the design document in full. Then follow this workflow exactly:\n\n"
        "**Git setup** (do this first, before any file changes):\n"
        "1. Capture the current branch name: git branch --show-current\n"
        f"2. Create and switch to a new branch: git checkout -b {branch_name}\n\n"
        "**Scaffolding** (do all of this on the new branch):\n"
        f"3. Create {workspace_dir}/CLAUDE.md with build, test, and lint commands "
        "appropriate for the technology stack described in the design.\n"
        "4. Scaffold the initial project structure inside the workspace directory: "
        "directory layout, configuration files, empty entry points, and dependency "
        "manifests with required packages listed.\n"
        "Do not implement any story logic — only the skeleton that lets Coding Agents "
        "start implementing immediately.\n\n"
        "**Commit and merge** (do this after all scaffolding is complete):\n"
        f"5. Stage and commit all changes in a single commit: git add -A && git commit -m 'scaffold project for {stem}'\n"
        f"6. Merge back into the original branch: git checkout <original-branch> && git merge {branch_name}\n"
        "(Replace <original-branch> with the branch name captured in step 1.)"
    )

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_project-initialiser"),
        allowed_tools=["Read", "Write", "Bash", "Glob"],
        permission_mode="acceptEdits",
        max_turns=200,
        model=model,
    )

    async for message in query(prompt=task, options=options):
        log_claude_message(conv_log_dir, agent_name, message, "project-init")

    append_run_log(run_log, agent_name, f"project initiated from: {design_path.name}")


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, design_path, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir)
