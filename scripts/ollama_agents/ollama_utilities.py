"""Shared Ollama utilities: tool definitions, ToolExecutor, and agent loops.

Imported by all ollama_* agent scripts. The two agent-loop variants are:

- ``run_agent_loop``: task-oriented; runs until the model stops requesting tool
  calls or ``max_turns`` is reached. Suited for coding agents and the BA agent.

- ``run_chat_loop``: interactive; after each model text response (no tool calls),
  prompts the user for input and feeds it back as a user message. Suited for
  the designer agent.
"""
import sys
from pathlib import Path

# Allow imports from the shared scripts/ directory.
sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import glob as glob_module
import json
import os
import re
import subprocess
from typing import Any

from ollama import AsyncClient, Message

from conversation_logger import log_ollama_response, log_ollama_tool_result

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_MODEL = "qwen2.5-coder"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
MAX_TURNS = 200
_PREVIEW_CHARS = 500


# ---------------------------------------------------------------------------
# Interactive session exceptions
# ---------------------------------------------------------------------------


class UserSkipRequest(Exception):
    """Raised by ask_user when the user types 'skip' — skip this story."""


class UserExitRequest(Exception):
    """Raised by ask_user when the user types 'exit'/'quit' or sends EOF."""

# ---------------------------------------------------------------------------
# Tool specifications (Ollama / OpenAI function-call format)
# ---------------------------------------------------------------------------

_TOOL_READ_FILE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "read_file",
        "description": (
            "Read the full contents of a file. "
            "Path may be absolute or relative to the working directory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
    },
}

_TOOL_WRITE_FILE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "write_file",
        "description": "Write (or overwrite) a file with the given content.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Full file content"},
            },
            "required": ["path", "content"],
        },
    },
}

_TOOL_EDIT_FILE: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "edit_file",
        "description": (
            "Replace the first occurrence of old_string with new_string inside a file. "
            "Returns an error if old_string is not found. "
            "Read the file first so old_string matches exactly."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to edit"},
                "old_string": {"type": "string", "description": "Exact text to find"},
                "new_string": {"type": "string", "description": "Replacement text"},
            },
            "required": ["path", "old_string", "new_string"],
        },
    },
}

_TOOL_BASH: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "bash",
        "description": (
            "Run a shell command in the working directory and return stdout + stderr. "
            "Timeout: 120 seconds."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute"},
            },
            "required": ["command"],
        },
    },
}

_TOOL_GLOB: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "glob",
        "description": (
            "Find files matching a glob pattern relative to the working directory. "
            "Returns a newline-separated list of absolute paths."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern, e.g. 'src/**/*.py'",
                },
                "directory": {
                    "type": "string",
                    "description": "Root directory for the search (default: working directory)",
                },
            },
            "required": ["pattern"],
        },
    },
}

_TOOL_GREP: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "grep",
        "description": (
            "Search file contents for a regex pattern. "
            "Returns matching lines with file paths and line numbers."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern to search for"},
                "path": {
                    "type": "string",
                    "description": "File or directory to search (default: working directory)",
                },
                "glob": {
                    "type": "string",
                    "description": "Restrict search to files matching this glob (e.g. '*.py')",
                },
            },
            "required": ["pattern"],
        },
    },
}

_TOOL_ASK_USER: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "ask_user",
        "description": (
            "Display a message or question to the user and return their typed response. "
            "Use this for all user interaction: presenting findings, asking clarifying "
            "questions, proposing solutions, and confirming before making changes. "
            "The user may type 'skip' to abandon this story or 'exit' to stop the resolver."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The message or question to display to the user",
                },
            },
            "required": ["question"],
        },
    },
}

# ---------------------------------------------------------------------------
# Tool groupings — import and use these in agent scripts
# ---------------------------------------------------------------------------

#: Full coding toolkit: read, write, edit, shell, file-search, content-search.
CODING_TOOLS: list[dict[str, Any]] = [
    _TOOL_READ_FILE,
    _TOOL_WRITE_FILE,
    _TOOL_EDIT_FILE,
    _TOOL_BASH,
    _TOOL_GLOB,
    _TOOL_GREP,
]

#: Business Analyst toolkit: read/write/list files + shell.
BA_TOOLS: list[dict[str, Any]] = [
    _TOOL_READ_FILE,
    _TOOL_WRITE_FILE,
    _TOOL_GLOB,
    _TOOL_BASH,
]

#: Designer toolkit: read/write files only (conversation handled by chat loop).
DESIGNER_TOOLS: list[dict[str, Any]] = [
    _TOOL_READ_FILE,
    _TOOL_WRITE_FILE,
    _TOOL_GLOB,
]

#: Resolver toolkit: inspect workspace + interactive user communication.
RESOLVER_TOOLS: list[dict[str, Any]] = [
    _TOOL_READ_FILE,
    _TOOL_WRITE_FILE,
    _TOOL_EDIT_FILE,
    _TOOL_GLOB,
    _TOOL_GREP,
    _TOOL_ASK_USER,
]

# ---------------------------------------------------------------------------
# Tool executor
# ---------------------------------------------------------------------------


class ToolExecutor:
    """Executes tool calls requested by the model.

    All relative paths are resolved against *cwd* (the working directory
    passed at construction time).
    """

    def __init__(self, cwd: Path) -> None:
        self._cwd = cwd

    def _resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else self._cwd / p

    # --- individual tools ---------------------------------------------------

    def read_file(self, path: str) -> str:
        try:
            return self._resolve(path).read_text()
        except FileNotFoundError:
            return f"ERROR: file not found: {path}"
        except Exception as exc:
            return f"ERROR: {exc}"

    def write_file(self, path: str, content: str) -> str:
        try:
            target = self._resolve(path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
            return f"OK: wrote {len(content)} chars to {path}"
        except Exception as exc:
            return f"ERROR: {exc}"

    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        try:
            target = self._resolve(path)
            original = target.read_text()
            if old_string not in original:
                return f"ERROR: old_string not found in {path}"
            target.write_text(original.replace(old_string, new_string, 1))
            return f"OK: edited {path}"
        except FileNotFoundError:
            return f"ERROR: file not found: {path}"
        except Exception as exc:
            return f"ERROR: {exc}"

    def bash(self, command: str) -> str:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=str(self._cwd),
                capture_output=True,
                text=True,
                timeout=120,
            )
            output = result.stdout
            if result.stderr:
                output += "\n[stderr]\n" + result.stderr
            if result.returncode != 0:
                output += f"\n[exit code: {result.returncode}]"
            return output.strip() or "(no output)"
        except subprocess.TimeoutExpired:
            return "ERROR: command timed out after 120 seconds"
        except Exception as exc:
            return f"ERROR: {exc}"

    def glob(self, pattern: str, directory: str = "") -> str:
        base = self._resolve(directory) if directory else self._cwd
        matches = sorted(glob_module.glob(str(base / pattern), recursive=True))
        return "\n".join(matches) if matches else "(no matches)"

    def grep(self, pattern: str, path: str = "", glob: str = "") -> str:
        search_path = self._resolve(path) if path else self._cwd
        include = ["--include", glob] if glob else []
        cmd = ["grep", "-rn", "-E", *include, pattern, str(search_path)]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return result.stdout.strip() or "(no matches)"
        except Exception as exc:
            return f"ERROR: {exc}"

    def ask_user(self, question: str) -> str:
        """Print *question* and return the user's typed response.

        Raises :class:`UserSkipRequest` if the user types ``skip``.
        Raises :class:`UserExitRequest` if the user types ``exit``/``quit``
        or sends EOF/Ctrl-C.
        """
        print(f"\n{question}", flush=True)
        try:
            response = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            raise UserExitRequest()
        if response.lower() in ("exit", "quit"):
            raise UserExitRequest()
        if response.lower() == "skip":
            raise UserSkipRequest()
        return response

    # --- dispatch -----------------------------------------------------------

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        """Dispatch a tool call by name and return its string result.

        Note: ``ask_user`` may raise :class:`UserSkipRequest` or
        :class:`UserExitRequest` — these are intentionally not caught here
        so they propagate through the agent loop to the caller.
        """
        handlers: dict[str, Any] = {
            "read_file": lambda a: self.read_file(a["path"]),
            "write_file": lambda a: self.write_file(a["path"], a["content"]),
            "edit_file": lambda a: self.edit_file(a["path"], a["old_string"], a["new_string"]),
            "bash": lambda a: self.bash(a["command"]),
            "glob": lambda a: self.glob(a["pattern"], a.get("directory", "")),
            "grep": lambda a: self.grep(a["pattern"], a.get("path", ""), a.get("glob", "")),
            "ask_user": lambda a: self.ask_user(a["question"]),
        }
        handler = handlers.get(name)
        if handler is None:
            return f"ERROR: unknown tool '{name}'"
        return handler(arguments)


# ---------------------------------------------------------------------------
# Helper: parse tool-call arguments (Ollama may return str or dict)
# ---------------------------------------------------------------------------


def _parse_tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            result = json.loads(raw)
            return result if isinstance(result, dict) else {}
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


# ---------------------------------------------------------------------------
# Helper: execute all tool calls in a response and append tool-result messages
# ---------------------------------------------------------------------------


def _try_extract_tool_calls_from_text(
    content: str,
    tool_names: set[str],
) -> list[tuple[str, dict[str, Any]]]:
    """Try to parse structured tool calls from a plain-text model response.

    Some local models emit tool call JSON as text rather than using the
    structured function-call mechanism.  This function scans *content* for
    JSON objects whose ``name`` or ``function`` key matches a known tool name
    and returns a list of ``(tool_name, arguments)`` pairs, preserving order
    and deduplicating by content.
    """
    # Strip markdown code fences so bare JSON can be parsed directly
    cleaned = re.sub(r"```(?:json)?\s*", "", content).replace("```", "").strip()

    found: list[tuple[str, dict[str, Any]]] = []
    seen: set[str] = set()

    def _try(s: str) -> None:
        try:
            obj = json.loads(s)
        except (json.JSONDecodeError, ValueError):
            return
        items: list[Any] = obj if isinstance(obj, list) else [obj]
        for item in items:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("function") or "").strip()
            args = item.get("arguments") or item.get("parameters") or {}
            if name in tool_names and isinstance(args, dict):
                key = f"{name}:{json.dumps(args, sort_keys=True)}"
                if key not in seen:
                    seen.add(key)
                    found.append((name, args))

    # Try the whole cleaned string first (handles responses that are pure JSON)
    _try(cleaned)

    # Then scan for JSON object substrings (handles JSON embedded in prose)
    for m in re.finditer(r"\{", cleaned):
        depth = 0
        for i, ch in enumerate(cleaned[m.start():], m.start()):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    _try(cleaned[m.start(): i + 1])
                    break

    return found


def _execute_calls(
    calls: list[tuple[str, dict[str, Any]]],
    messages: list[Message],
    executor: ToolExecutor,
    agent_name: str = "",
    conv_log_dir: Path | None = None,
    context: str = "",
) -> None:
    """Execute a list of ``(tool_name, arguments)`` pairs, print results, and append tool messages."""
    for name, arguments in calls:
        print(f"\n[tool:{name}] {json.dumps(arguments, ensure_ascii=False)}", flush=True)
        result = executor.execute(name, arguments)
        preview = result if len(result) <= _PREVIEW_CHARS else result[:_PREVIEW_CHARS] + "…"
        print(f"[result:ok] {preview}", flush=True)
        messages.append(Message(role="tool", content=result))
        log_ollama_tool_result(conv_log_dir, agent_name, name, arguments, result, context)


def _handle_tool_calls(
    msg: Message,
    messages: list[Message],
    executor: ToolExecutor,
    agent_name: str,
    conv_log_dir: Path | None = None,
    context: str = "",
) -> None:
    """Execute every structured tool call in *msg*, print results, and append them to *messages*."""
    calls = [
        (tool_call.function.name, _parse_tool_args(tool_call.function.arguments))
        for tool_call in (msg.tool_calls or [])
    ]
    _execute_calls(calls, messages, executor, agent_name, conv_log_dir, context)


def _handle_text_tool_calls(
    msg: Message,
    messages: list[Message],
    executor: ToolExecutor,
    agent_name: str,
    tools: list[dict[str, Any]],
    conv_log_dir: Path | None = None,
    context: str = "",
) -> bool:
    """Check *msg.content* for embedded JSON tool calls and execute any found.

    Some local models output tool call JSON as plain text rather than using the
    structured function-call mechanism.  Returns ``True`` if at least one call
    was detected and executed so callers can ``continue`` the agent loop.
    """
    if not msg.content:
        return False
    tool_names = {t["function"]["name"] for t in tools}
    calls = _try_extract_tool_calls_from_text(msg.content, tool_names)
    if not calls:
        return False
    print(f"\n[{agent_name}] Tool call detected in text response — executing.", flush=True)
    messages.append(msg)
    _execute_calls(calls, messages, executor, agent_name, conv_log_dir, context)
    return True


# ---------------------------------------------------------------------------
# Agent loop: task-oriented (non-interactive)
# ---------------------------------------------------------------------------


async def run_agent_loop(
    messages: list[Message],
    client: AsyncClient,
    model: str,
    tools: list[dict[str, Any]],
    executor: ToolExecutor,
    agent_name: str,
    max_turns: int = MAX_TURNS,
    system_prompt: str = "",
    conv_log_dir: Path | None = None,
    context: str = "",
) -> None:
    """Drive a task-oriented agentic loop.

    Sends *messages* to the model, executes any tool calls, appends results,
    and repeats until the model produces a response with no tool calls or
    *max_turns* is reached.

    If *system_prompt* is provided it is inserted as a ``system`` message at
    index 0 of *messages* before the first call so the full history remains
    in one list throughout the loop.

    *messages* is mutated in place so callers can inspect the full history.
    """
    if system_prompt:
        messages.insert(0, Message(role="system", content=system_prompt))

    for turn in range(max_turns):
        response = await client.chat(
            model=model,
            messages=messages,
            tools=tools,
            options={"num_ctx": 32768},
        )
        log_ollama_response(conv_log_dir, agent_name, response, context)

        msg = response.message
        if msg.content:
            print(f"\n[{agent_name}] {msg.content}", flush=True)

        if not msg.tool_calls:
            # Check whether the model embedded tool call JSON in plain text
            if _handle_text_tool_calls(msg, messages, executor, agent_name, tools, conv_log_dir, context):
                continue

            print(f"[{agent_name}] Turn {turn + 1}: done (no tool calls).", flush=True)
            return

        messages.append(msg)
        _handle_tool_calls(msg, messages, executor, agent_name, conv_log_dir, context)

    print(f"[{agent_name}] Reached max turns ({max_turns}) — stopping.", flush=True)


# ---------------------------------------------------------------------------
# Agent loop: chat / interactive
# ---------------------------------------------------------------------------


async def run_chat_loop(
    messages: list[Message],
    client: AsyncClient,
    model: str,
    tools: list[dict[str, Any]],
    executor: ToolExecutor,
    agent_name: str,
    max_turns: int = MAX_TURNS,
    exit_phrases: tuple[str, ...] = ("exit", "quit", "bye"),
    system_prompt: str = "",
    conv_log_dir: Path | None = None,
    context: str = "",
) -> None:
    """Drive an interactive chat loop.

    After each model text response (no tool calls) the user is prompted for
    input. Tool calls are executed silently and fed back to the model without
    prompting the user. The loop ends when the user types an exit phrase,
    sends EOF/Ctrl-C, or *max_turns* is reached.

    If *system_prompt* is provided it is inserted as a ``system`` message at
    index 0 of *messages* before the first call.

    *messages* is mutated in place so callers can inspect the full history.
    """
    if system_prompt:
        messages.insert(0, Message(role="system", content=system_prompt))

    for turn in range(max_turns):
        response = await client.chat(
            model=model,
            messages=messages,
            tools=tools,
            options={"num_ctx": 32768},
        )
        log_ollama_response(conv_log_dir, agent_name, response, context)

        msg = response.message
        if msg.content:
            print(f"\n{msg.content}", flush=True)

        if msg.tool_calls:
            # Execute tools and let the model continue without user prompt
            messages.append(msg)
            _handle_tool_calls(msg, messages, executor, agent_name, conv_log_dir, context)
            continue

        # No structured tool calls — check whether the model embedded a tool
        # call as plain-text JSON (common with smaller local models).
        if _handle_text_tool_calls(msg, messages, executor, agent_name, tools, conv_log_dir, context):
            continue

        # No tool calls — hand back to the user
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n[{agent_name}] Session ended.")
            return

        if not user_input:
            continue

        if user_input.lower() in exit_phrases:
            print(f"[{agent_name}] Session ended.")
            return

        messages.append(msg)  # assistant turn
        messages.append(Message(role="user", content=user_input))

    print(f"[{agent_name}] Reached max turns ({max_turns}) — stopping.", flush=True)


# ---------------------------------------------------------------------------
# Convenience: create an Ollama async client
# ---------------------------------------------------------------------------


def make_client(host: str = DEFAULT_OLLAMA_HOST) -> AsyncClient:
    """Return a configured :class:`AsyncClient` for the given Ollama host."""
    return AsyncClient(host=host)


# ---------------------------------------------------------------------------
# Convenience: add shared Ollama CLI arguments to an argparse parser
# ---------------------------------------------------------------------------


def add_ollama_args(
    parser: argparse.ArgumentParser,
    default_model: str = DEFAULT_MODEL,
    default_agent_name: str = "ollama-agent",
) -> None:
    """Attach the standard Ollama flags to *parser* (mutates in place)."""
    parser.add_argument(
        "--model",
        default=default_model,
        help=f"Ollama model to use (default: {default_model})",
    )
    parser.add_argument(
        "--ollama-host",
        default=os.environ.get("OLLAMA_HOST", DEFAULT_OLLAMA_HOST),
        help=f"Ollama API base URL (default: {DEFAULT_OLLAMA_HOST}, or $OLLAMA_HOST)",
    )
    parser.add_argument(
        "--conv-log-dir",
        default="",
        help="Directory for per-agent conversation JSONL logs; file named <agent-name>_log.jsonl (optional)",
    )
    parser.add_argument(
        "--run-log",
        default="",
        help="Path to run-log.json file for pipeline event logging (optional)",
    )
    parser.add_argument(
        "--agent-name",
        default=default_agent_name,
        help=f"Name used in logs (default: {default_agent_name})",
    )
