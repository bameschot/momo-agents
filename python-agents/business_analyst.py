"""Business Analyst Agent — reads a design document and writes story files."""
import argparse
import anyio
import sys
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
ROLES_DIR = PROJECT_ROOT / "roles"

DEFAULT_MODEL = "claude-sonnet-4-6"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Business Analyst Agent")
    parser.add_argument(
        "--design",
        required=True,
        help="Path to the design document (e.g. design/my-feature.md)",
    )
    parser.add_argument(
        "--stories-dir",
        default=str(PROJECT_ROOT / "stories"),
        help="Directory where story files are written (default: <project-root>/stories)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Claude model to use (default: {DEFAULT_MODEL})",
    )
    return parser.parse_args()


def _system_prompt() -> str:
    return (ROLES_DIR / "business-analyst.md").read_text()


async def run(design_path: Path, stories_dir: Path, model: str) -> None:
    if not design_path.exists():
        print(f"Error: design file not found: {design_path}", file=sys.stderr)
        sys.exit(1)

    stories_dir.mkdir(parents=True, exist_ok=True)

    # Determine the next story number by counting existing story files.
    existing = sorted(stories_dir.glob("STORY-*.md"))
    next_index = len(existing) + 1

    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Design document: {design_path}\n"
        f"Stories output directory: {stories_dir}\n"
        f"Next story number to use: {next_index:03d} (zero-padded three digits)\n\n"
        "Read the design document in full. Decompose it into an ordered set of discrete, "
        "implementable stories and write each one to the stories directory as STORY-NNN.md. "
        "Follow the story file format defined in your role exactly. "
        "Do not leave open questions — resolve ambiguities from the design before writing."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write", "Glob"],
        permission_mode="acceptEdits",
        max_turns=200,
        model=model,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[Business Analyst Agent finished — stop reason: {message.stop_reason}]")


if __name__ == "__main__":
    args = _parse_args()
    design_path = Path(args.design)
    if not design_path.is_absolute():
        design_path = PROJECT_ROOT / design_path
    stories_dir = Path(args.stories_dir)
    if not stories_dir.is_absolute():
        stories_dir = PROJECT_ROOT / stories_dir
    anyio.run(run, design_path, stories_dir, args.model)
