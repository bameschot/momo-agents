"""Designer Agent — interactive Q&A session that produces design/<feature>.md."""
import anyio
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, TextBlock, query

PROJECT_ROOT = Path(__file__).parent.parent
DESIGN_DIR = PROJECT_ROOT / "design"
ROLES_DIR = PROJECT_ROOT / "roles"


def _system_prompt() -> str:
    return (ROLES_DIR / "designer.md").read_text()


async def run() -> None:
    task = (
        f"Project root: {PROJECT_ROOT}\n"
        f"Design output directory: {DESIGN_DIR}\n\n"
        "Begin the design session now. Greet the user and ask what they want to build. "
        "Use the AskUserQuestion tool to conduct the Q&A. "
        "Ask clarifying questions freely until you have a complete, unambiguous picture "
        "of the requirements. "
        "When the user types the command 'write', produce the design document and save it "
        f"to {DESIGN_DIR}/<feature-name>.md, where <feature-name> is a short kebab-case "
        "identifier derived from the feature being designed."
    )

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["AskUserQuestion", "Read", "Write"],
        permission_mode="default",
        max_turns=500,
    )

    async for message in query(prompt=task, options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            print(f"\n\n[Designer Agent finished — stop reason: {message.stop_reason}]")


if __name__ == "__main__":
    anyio.run(run)
