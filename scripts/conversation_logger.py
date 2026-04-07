"""Central conversation logger — writes one JSONL record per model message to a per-agent log file.

Usage (Claude agents):
    from conversation_logger import ConversationLogger
    conv_logger = ConversationLogger.from_log_dir(conv_log_dir, agent_name)
    async for message in query(...):
        conv_logger.log_claude_message(message, context)

Usage (Ollama agents — via ollama_utilities run_agent_loop / run_chat_loop):
    await run_agent_loop(..., conv_logger=conv_logger, context="STORY-001")

Each JSONL record contains:
    ts              ISO-8601 UTC timestamp
    agent           agent name
    context         story (STORY-NNN) or phase being worked on
    role            assistant | user | system | result | tool
    content         message body (str or list of content blocks)
    tool_calls      list of tool call dicts (Ollama only, omitted when None)
    input_tokens    prompt tokens (0 when unavailable)
    output_tokens   completion tokens (0 when unavailable)
    cache_read_tokens
    cache_write_tokens
    cost_usd        USD cost (0.0 when unavailable)
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ConversationLogger:
    """Logs raw model interactions to a per-agent JSONL file."""

    def __init__(self, log_file: Path | None, agent: str) -> None:
        self._log_file = log_file
        self._agent = agent

    @classmethod
    def from_log_dir(cls, log_dir: Path | None, agent_name: str) -> "ConversationLogger":
        """Return a logger that writes to ``log_dir/<agent_name>_log.jsonl``.

        Returns a no-op logger when *log_dir* is None.
        """
        if log_dir is None:
            return cls(None, agent_name)
        return cls(log_dir / f"{agent_name}_log.jsonl", agent_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def log_claude_message(self, message: Any, context: str) -> None:
        """Log a Claude SDK message (AssistantMessage, UserMessage, SystemMessage, ResultMessage)."""
        if self._log_file is None:
            return
        entry = self._build_claude_entry(message, context)
        if entry is not None:
            self._write(entry)

    def log_ollama_response(self, response: Any, context: str) -> None:
        """Log an Ollama ChatResponse object."""
        if self._log_file is None:
            return
        self._write(self._build_ollama_entry(response, context))

    # ------------------------------------------------------------------
    # Claude entry builder
    # ------------------------------------------------------------------

    def _build_claude_entry(self, message: Any, context: str) -> dict[str, Any] | None:
        try:
            from claude_agent_sdk import (  # noqa: PLC0415
                AssistantMessage,
                ResultMessage,
                SystemMessage,
                TextBlock,
                ThinkingBlock,
                ToolResultBlock,
                ToolUseBlock,
                UserMessage,
            )
        except ImportError:
            return None

        base: dict[str, Any] = {
            "ts": self._ts(),
            "agent": self._agent,
            "context": context,
        }

        if isinstance(message, AssistantMessage):
            content: list[dict[str, Any]] = []
            for block in message.content:
                if isinstance(block, TextBlock):
                    content.append({"type": "text", "text": block.text})
                elif isinstance(block, ToolUseBlock):
                    content.append({"type": "tool_use", "name": block.name, "input": block.input})
                elif isinstance(block, ToolResultBlock):
                    content.append({
                        "type": "tool_result",
                        "content": str(block.content)[:2000],
                        "is_error": block.is_error,
                    })
                elif isinstance(block, ThinkingBlock):
                    content.append({"type": "thinking", "thinking": block.thinking})
            usage = message.usage or {}
            return {
                **base,
                "role": "assistant",
                "content": content,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
                "cost_usd": 0.0,
            }

        if isinstance(message, UserMessage):
            raw = message.content
            if isinstance(raw, str):
                user_content: Any = raw
            else:
                parts: list[dict[str, Any]] = []
                for block in raw:
                    if isinstance(block, ToolResultBlock):
                        parts.append({
                            "type": "tool_result",
                            "content": str(block.content)[:2000],
                            "is_error": block.is_error,
                        })
                user_content = parts
            return {**base, "role": "user", "content": user_content}

        if isinstance(message, SystemMessage):
            return {**base, "role": "system", "subtype": message.subtype}

        if isinstance(message, ResultMessage):
            usage = message.usage or {}
            return {
                **base,
                "role": "result",
                "stop_reason": message.stop_reason,
                "num_turns": message.num_turns,
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
                "cost_usd": round(message.total_cost_usd, 6) if message.total_cost_usd is not None else 0.0,
            }

        return None

    # ------------------------------------------------------------------
    # Ollama entry builder
    # ------------------------------------------------------------------

    def _build_ollama_entry(self, response: Any, context: str) -> dict[str, Any]:
        msg = response.message
        tool_calls = None
        if msg.tool_calls:
            tool_calls = [
                {"name": tc.function.name, "arguments": tc.function.arguments}
                for tc in msg.tool_calls
            ]
        return {
            "ts": self._ts(),
            "agent": self._agent,
            "context": context,
            "role": msg.role,
            "content": msg.content or "",
            "tool_calls": tool_calls,
            "input_tokens": getattr(response, "prompt_eval_count", 0) or 0,
            "output_tokens": getattr(response, "eval_count", 0) or 0,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "cost_usd": 0.0,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _ts(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _write(self, entry: dict[str, Any]) -> None:
        assert self._log_file is not None  # guarded by callers
        self._log_file.parent.mkdir(parents=True, exist_ok=True)
        with self._log_file.open("a") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
