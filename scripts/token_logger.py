"""Shared token-usage logging and console-output utility for all momo-agents."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MAX_RESULT_CHARS = 500  # truncation limit for tool result content in console output


def fmt_usage(usage: dict | None) -> str:
    """Return a compact, human-readable token summary for inline printing.

    Example: ``[in=1,234 out=567 cache_r=8,901 cache_w=234]``
    Returns an empty string when *usage* is None or empty.
    """
    if not usage:
        return ""
    parts = []
    if v := usage.get("input_tokens"):
        parts.append(f"in={v:,}")
    if v := usage.get("output_tokens"):
        parts.append(f"out={v:,}")
    if v := usage.get("cache_read_input_tokens"):
        parts.append(f"cache_r={v:,}")
    if v := usage.get("cache_creation_input_tokens"):
        parts.append(f"cache_w={v:,}")
    return f"[{' '.join(parts)}]" if parts else ""


def print_message(message: Any) -> None:
    """Print every content block of any SDK message to stdout.

    Handles AssistantMessage, UserMessage, SystemMessage, and ResultMessage.
    Token usage is appended at the end of each AssistantMessage; total cost
    and usage are shown on the ResultMessage line.
    """
    from claude_agent_sdk import (  # imported here to avoid a top-level circular dep
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
        UserMessage,
    )

    if isinstance(message, AssistantMessage):
        for block in message.content:
            if isinstance(block, TextBlock):
                print(block.text, end="", flush=True)
            elif isinstance(block, ToolUseBlock):
                args = json.dumps(block.input, ensure_ascii=False)
                print(f"\n[tool:{block.name}] {args}", flush=True)
            elif isinstance(block, ToolResultBlock):
                text = _format_tool_content(block.content)
                status = "error" if block.is_error else "ok"
                print(f"\n[result:{status}] {text}", flush=True)
            elif isinstance(block, ThinkingBlock):
                preview = block.thinking[:200] + "…" if len(block.thinking) > 200 else block.thinking
                print(f"\n[thinking] {preview}", flush=True)
        if usage_str := fmt_usage(message.usage):
            print(f"\n{usage_str}", flush=True)

    elif isinstance(message, UserMessage):
        content = message.content
        if isinstance(content, str):
            print(f"\n[user] {content}", flush=True)
        else:
            for block in content:
                if isinstance(block, ToolResultBlock):
                    text = _format_tool_content(block.content)
                    status = "error" if block.is_error else "ok"
                    print(f"\n[result:{status}] {text}", flush=True)

    elif isinstance(message, SystemMessage):
        print(f"\n[system:{message.subtype}]", flush=True)

    elif isinstance(message, ResultMessage):
        cost = f"${message.total_cost_usd:.4f}" if message.total_cost_usd is not None else "n/a"
        usage_str = fmt_usage(message.usage)
        print(
            f"\n[done] stop={message.stop_reason} turns={message.num_turns} "
            f"cost={cost} {usage_str}",
            flush=True,
        )


def _format_tool_content(content: Any) -> str:
    """Format tool result content for console output, truncating if necessary."""
    if content is None:
        return ""
    text = json.dumps(content, ensure_ascii=False) if isinstance(content, list) else str(content)
    if len(text) > _MAX_RESULT_CHARS:
        text = text[:_MAX_RESULT_CHARS] + "…"
    return text


def log_usage(
    log_file: Path | None,
    agent: str,
    usage: dict | None,
    cost_usd: float | None = None,
) -> None:
    """Write one JSONL record immediately to *log_file* for each call.

    Safe to call with ``usage=None`` and/or ``cost_usd=None`` (no-op when both
    are absent) so callers need no guard logic.
    The file and its parent directory are created automatically.
    """
    if log_file is None or (not usage and cost_usd is None):
        return

    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "input_tokens": usage.get("input_tokens", 0) if usage else 0,
        "output_tokens": usage.get("output_tokens", 0) if usage else 0,
        "cache_read_tokens": usage.get("cache_read_input_tokens", 0) if usage else 0,
        "cache_write_tokens": usage.get("cache_creation_input_tokens", 0) if usage else 0,
        "cost_usd": round(cost_usd, 6) if cost_usd is not None else 0.0,
    }
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
