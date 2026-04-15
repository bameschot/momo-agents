"""Project Initialiser Agent — scaffolds workspace/ from a design document."""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import anyio

from claude_agent_sdk import ClaudeAgentOptions, query

from agent_utilities import PROJECT_ROOT, append_run_log, load_role, resolve_path
from claude_utilities import build_common_arg_parser
from conversation_logger import log_claude_message, print_claude_message

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _parse_args():
    parser = build_common_arg_parser(
        description="Project Initialiser Agent",
        default_model=DEFAULT_MODEL,
        default_agent_name="project-initialiser",
    )
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. design/my-feature.md)",
    )
    return parser.parse_args()


async def run(design_path: Path, workspace_dir: Path, model: str, run_log: Path | None, agent_name: str, conv_log_dir: Path | None, effort: str = "medium") -> None:
    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    task = (
        f"Workspace: {workspace_dir}\n"
        f"Design document: {design_path}\n\n"
        "Read the design document in full. Then follow this workflow exactly:\n\n"
        "**Scaffolding**:\n"
        f"1. Create {workspace_dir}/CLAUDE.md with build, test, and lint commands "
        "appropriate for the technology stack described in the design.\n"
        "2. Scaffold the initial project structure inside the workspace directory: "
        "directory layout, configuration files, empty entry points, and dependency "
        "manifests with required packages listed. "
        "Always ensure `.sentinels/` is listed in `.gitignore`.\n"
        "3. After all files are written, perform an initial commit: "
        "run `git add -A` then `git commit -m \"chore: initial project scaffold\"`.\n"
        "Do not implement any story logic — only the skeleton that lets Coding Agents "
        "start implementing immediately.\n\n"
    )

    options = ClaudeAgentOptions(
        cwd=str(workspace_dir),
        system_prompt=load_role("claude_roles/claude_project-initialiser"),
        allowed_tools=["Read", "Write", "Bash", "Glob"],
        permission_mode="acceptEdits",
        max_turns=200,
        model=model,
        effort=effort,
    )

    async for message in query(prompt=task, options=options):
        print_claude_message(agent_name, message)
        log_claude_message(conv_log_dir, agent_name, message, "project-init")

    append_run_log(run_log, agent_name, f"project initiated from: {design_path.name}")


if __name__ == "__main__":
    args = _parse_args()
    design_path = resolve_path(args.design)
    workspace_dir = resolve_path(args.workspace_dir)
    run_log = Path(args.run_log) if args.run_log else None
    conv_log_dir = Path(args.conv_log_dir) if args.conv_log_dir else None
    anyio.run(run, design_path, workspace_dir, args.model, run_log, args.agent_name, conv_log_dir, args.effort)
