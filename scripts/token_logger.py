"""Shared token-usage logging and console-output utility for all momo-agents."""
import json
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any

# Flush interval in seconds — accumulated tokens are written at most this often.
_FLUSH_INTERVAL = 15.0

# Per-agent accumulator: agent -> {"last_flush": float, "input": int, "output": int,
#                                   "cache_read": int, "cache_write": int}
_accumulators: dict[str, dict] = {}


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
    """Accumulate token counts and cost from a message and flush to *log_file*
    at most every 30 seconds.  The final flush is guaranteed on exit via
    :func:`flush_all`.

    Safe to call with ``usage=None`` and/or ``cost_usd=None`` (no-op when both
    are absent) so callers need no guard logic.
    The file and its parent directory are created automatically on first flush.
    """
    if log_file is None or (not usage and cost_usd is None):
        return

    now = monotonic()
    acc = _accumulators.setdefault(
        agent,
        {
            "last_flush": now,
            "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
            "cost": 0.0,
            "log_file": log_file,
        },
    )

    if usage:
        acc["input"] += usage.get("input_tokens", 0)
        acc["output"] += usage.get("output_tokens", 0)
        acc["cache_read"] += usage.get("cache_read_input_tokens", 0)
        acc["cache_write"] += usage.get("cache_creation_input_tokens", 0)
    if cost_usd is not None:
        acc["cost"] += cost_usd

    if now - acc["last_flush"] >= _FLUSH_INTERVAL:
        _flush(agent, acc)


def flush_all() -> None:
    """Flush any remaining accumulated tokens and cost for all agents and print
    a per-agent cost summary to stdout.  Call once on process exit."""
    for agent, acc in _accumulators.items():
        if acc["input"] or acc["output"] or acc["cache_read"] or acc["cache_write"] or acc["cost"]:
            _flush(agent, acc)


def _flush(agent: str, acc: dict) -> None:
    """Write one JSONL record for *agent* and reset the accumulator."""
    log_file: Path = acc["log_file"]
    entry = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "agent": agent,
        "input_tokens": acc["input"],
        "output_tokens": acc["output"],
        "cache_read_tokens": acc["cache_read"],
        "cache_write_tokens": acc["cache_write"],
        "cost_usd": round(acc["cost"], 6),
    }
    log_file.parent.mkdir(parents=True, exist_ok=True)
    with log_file.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")

    acc["input"] = 0
    acc["output"] = 0
    acc["cache_read"] = 0
    acc["cache_write"] = 0
    acc["cost"] = 0.0
    acc["last_flush"] = monotonic()
