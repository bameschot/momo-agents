"""Project Initialiser Agent — scaffolds workspace/ from a design document."""
import argparse
import anyio
import sys
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
ROLES_DIR = PROJECT_ROOT / "roles"


def _system_prompt() -> str:
    return (ROLES_DIR / "project-initialiser.md").read_text()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Project Initialiser Agent")
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. design/my-feature.md)",
    )
    return parser.parse_args()


async def run(design_path: Path) -> None:
    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Design document: {design_path}\n"
        f"Workspace directory: {WORKSPACE_DIR}\n\n"
        "Read the design document in full. Then:\n"
        f"1. Create {WORKSPACE_DIR}/CLAUDE.md with build, test, and lint commands "
        "appropriate for the technology stack described in the design.\n"
        "2. Scaffold the initial project structure inside the workspace directory: "
        "directory layout, configuration files, empty entry points, and dependency "
        "manifests with required packages listed.\n"
        "Do not implement any story logic — only the skeleton that lets Coding Agents "
        "start implementing immediately."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write", "Bash", "Glob"],
        permission_mode="acceptEdits",
        max_turns=200,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(
                f"\n\n[Project Initialiser Agent finished — stop reason: {message.stop_reason}]"
            )


if __name__ == "__main__":
    args = _parse_args()
    design_path = Path(args.design)
    if not design_path.is_absolute():
        design_path = PROJECT_ROOT / design_path
    anyio.run(run, design_path)
