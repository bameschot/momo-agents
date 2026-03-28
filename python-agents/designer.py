"""Designer Agent — interactive multi-turn Q&A session that produces design/<feature>.new.md."""
import anyio
import sys
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
)

PROJECT_ROOT = Path(__file__).parent.parent
DESIGN_DIR = PROJECT_ROOT / "design"
ROLES_DIR = PROJECT_ROOT / "roles"

INITIAL_PROMPT = (
    f"Project root: {PROJECT_ROOT}\n"
    f"Design output directory: {DESIGN_DIR}\n\n"
    "Begin the design session. Greet the user and ask what they want to build. "
    "Ask clarifying questions freely until you have a complete, unambiguous picture "
    "of the requirements.\n\n"
    "File naming rules:\n"
    f"- Always save designs as {DESIGN_DIR}/<feature-name>.new.md, where <feature-name> "
    "is a short kebab-case identifier derived from what is being designed.\n"
    f"- If {DESIGN_DIR}/<feature-name>.processed.md already exists (an earlier version "
    "was processed by the Business Analyst), still write to <feature-name>.new.md — "
    "this signals the BA to re-process the updated design.\n"
    "- Never write to <feature-name>.processed.md directly.\n\n"
    "When the user says 'write', produce and save the design document using these rules."
)


def _system_prompt() -> str:
    return (ROLES_DIR / "designer.md").read_text()


async def _stream_response(client: ClaudeSDKClient) -> str | None:
    """Stream and print the agent's response. Returns stop_reason."""
    stop_reason = None
    async for message in client.receive_response():
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text, end="", flush=True)
        elif isinstance(message, ResultMessage):
            stop_reason = message.stop_reason
    return stop_reason


async def run() -> None:
    DESIGN_DIR.mkdir(parents=True, exist_ok=True)

    options = ClaudeAgentOptions(
        cwd=str(PROJECT_ROOT),
        system_prompt=_system_prompt(),
        allowed_tools=["Read", "Write"],
        permission_mode="acceptEdits",
        max_turns=50,
    )

    async with ClaudeSDKClient(options=options) as client:
        # Initial greeting turn
        await client.query(INITIAL_PROMPT)
        await _stream_response(client)
        print()  # newline after agent response

        # Conversation loop — user drives each turn
        while True:
            try:
                user_input = input("\nYou: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n[Designer session ended]")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "bye"):
                print("[Designer session ended]")
                break

            await client.query(user_input)
            stop_reason = await _stream_response(client)
            print()

            # If agent wrote the design doc and finished naturally, offer to exit
            if stop_reason == "end_turn" and user_input.lower() == "write":
                print("\n[Design saved as .new.md — the Business Analyst will pick it up automatically.]")
                print("[Type 'exit' to close or continue refining (type 'write' again to re-queue).]")


if __name__ == "__main__":
    anyio.run(run)
