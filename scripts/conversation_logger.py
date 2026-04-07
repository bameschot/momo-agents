"""Central conversation logger — writes one JSONL record per model message to a per-agent log file.

Usage (Claude agents):
    from conversation_logger import log_claude_message
    async for message in query(...):
        log_claude_message(conv_log_dir, agent_name, message, context)

Usage (Ollama agents — via ollama_utilities run_agent_loop / run_chat_loop):
    await run_agent_loop(..., conv_log_dir=conv_log_dir, context="STORY-001")

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


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def log_claude_message(log_dir: Path | None, agent_name: str, message: Any, context: str) -> None:
    """Log a Claude SDK message (AssistantMessage, UserMessage, SystemMessage, ResultMessage)."""
    if log_dir is None:
        return
    entry = _build_claude_entry(agent_name, message, context)
    if entry is not None:
        _write(log_dir / f"{agent_name}_log.jsonl", entry)


def log_ollama_response(log_dir: Path | None, agent_name: str, response: Any, context: str) -> None:
    """Log an Ollama ChatResponse object."""
    if log_dir is None:
        return
    _write(log_dir / f"{agent_name}_log.jsonl", _build_ollama_entry(agent_name, response, context))


# ------------------------------------------------------------------
# Claude entry builder
# ------------------------------------------------------------------

def _build_claude_entry(agent_name: str, message: Any, context: str) -> dict[str, Any] | None:
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
        "ts": _ts(),
        "agent": agent_name,
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

def _build_ollama_entry(agent_name: str, response: Any, context: str) -> dict[str, Any]:
    msg = response.message
    tool_calls = None
    if msg.tool_calls:
        tool_calls = [
            {"name": tc.function.name, "arguments": tc.function.arguments}
            for tc in msg.tool_calls
        ]
    return {
        "ts": _ts(),
        "agent": agent_name,
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

def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(log_file: Path, entry: dict[str, Any]) -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
