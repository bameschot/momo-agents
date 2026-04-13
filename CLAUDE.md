# CLAUDE.md

This file provides guidance for AI assistants (Claude Code and others) working in this repository.

## Project Overview

**momo-agents** is a Python project for building coding agents powered by the Claude Agent SDK. A team of specialised agents collaborate over the filesystem to take a feature idea from concept through to working, tested code.

Coding agents work in **isolated workspace copies** — each story is implemented in a private temp directory inside `.sentinels/` so parallel agents never touch each other's files. Completed workspaces are zipped into a `merge-queue/` folder, and a dedicated **Merger Agent** commits and merges them into the shared workspace git repository in story order.

- **Author**: bameschot
- **License**: MIT (2026)
- **Purpose**: Developing AI coding agents using the Claude Agent SDK

## Repository Structure

```
momo-agents/
├── CLAUDE.md               # This file
├── README.md               # Project overview
├── LICENSE                 # MIT License
├── pyproject.toml          # Project metadata and dependencies
├── requirements.txt        # Pip-compatible dependency list (mirrors pyproject.toml extras)
├── bundle-workspace.py     # Packages a project workspace into a named zip file
├── git_log_exporter.py     # Exports git commit metadata to JSONL format
├── run_report.py           # Generates a pipeline run report from run-log.jsonl and token logs
├── scripts/                # Python agent and utility implementations
│   ├── agent_utilities.py          # Shared helpers (path resolution, run-log, workspace copy/zip/merge)
│   ├── token_logger.py             # Shared JSONL token-usage logger and console printer
│   ├── story_orchestrator.py               # Non-LLM utility; shared by all agent types; marks stories ready when deps are met
│   ├── claude_agents/              # Agents backed by the Claude Agent SDK
│   │   ├── claude_designer_agent.py             # Interactive design session → workspace/design/<feature>.md
│   │   ├── claude_business_analyst_agent.py     # Decomposes design doc into story files
│   │   ├── claude_project_initialiser_agent.py  # Scaffolds workspace/ from design; writes workspace/CLAUDE.md
│   │   ├── claude_junior_coding_agent.py        # Claims easy stories; works in isolated workspace copy
│   │   ├── claude_senior_coding_agent.py        # Claims medium/hard stories; works in isolated workspace copy
│   │   └── claude_merger_agent.py               # Merges story zips from merge-queue into main branch
│   └── ollama_agents/              # Agents backed by a local Ollama instance
│       ├── ollama_utilities.py                      # Shared tool defs, ToolExecutor, agent loops, and text-tool-call fallback helpers
│       ├── ollama_designer_agent.py                 # Interactive design session (chat loop)
│       ├── ollama_business_analyst_agent.py         # Decomposes design doc into story files
│       ├── ollama_project_initialiser_agent.py      # Scaffolds workspace/ from design doc
│       ├── ollama_junior_coding_agent.py            # Claims easy stories; works in isolated workspace copy
│       ├── ollama_senior_coding_agent.py            # Claims medium/hard stories; works in isolated workspace copy
│       └── ollama_merger_agent.py                   # Merges story zips from merge-queue into main branch
├── roles/                  # System prompt files (one per LLM agent)
│   ├── claude_roles/                    # Prompts for the Claude backend
│   │   ├── claude_designer.md
│   │   ├── claude_business-analyst.md
│   │   ├── claude_project-initialiser.md
│   │   ├── claude_junior-coding-agent.md
│   │   ├── claude_senior-coding-agent.md
│   │   └── claude_merger-agent.md
│   └── ollama_roles/                    # Prompts for the Ollama backend (tool-aware variants)
│       ├── ollama-designer.md
│       ├── ollama-business-analyst.md
│       ├── ollama-project-initialiser.md
│       ├── ollama-junior-coding-agent.md
│       ├── ollama-senior-coding-agent.md
│       └── ollama-merger-agent.md
├── generated-test-applications/  # Sample outputs from pipeline test runs
├── workspace/              # All generated artefacts
│   ├── CLAUDE.md           # Build/test/lint instructions; start gate for all agents
│   ├── design/             # Designer Agent outputs (<feature>.new.md / <feature>.processed.md)
│   ├── stories/            # Story files (complexity + state encoded in filename)
│   ├── .sentinels/         # Runtime coordination files (created by start-team.sh)
│   │   ├── STORY-NNN/      #   Isolated temp workspace for a coding agent (deleted after use)
│   │   ├── merge-queue/    #   Zipped temp workspaces awaiting the Merger Agent
│   │   └── merge-STORY-NNN/ #  Staging dir used by Merger to unzip before git operations
│   ├── src/
│   └── tests/
├── start-team.sh           # Launches all agents simultaneously in named terminal windows
├── reset-team.sh           # Wipes all artefacts; resets to clean state
├── reset-stories.sh        # Resets story files only (keeps generated code)
├── status.sh               # Live story-state summary
└── watchdog.sh             # Resets stale .working.md files after 10 min; skips merge-queued stories
```

## Technology Stack

| Category        | Tool(s)                                          |
|----------------|--------------------------------------------------|
| Language        | Python 3.11+                                     |
| Package manager | uv (preferred)                                   |
| Linter          | Ruff                                             |
| Type checker    | mypy                                             |
| Test runner     | pytest                                           |
| AI backend      | Claude Agent SDK (`claude-agent-sdk`)            |
| Local AI backend| Ollama (`ollama>=0.4`) — optional extra          |

## Development Setup

```bash
# Clone the repository
git clone https://github.com/bameschot/momo-agents.git
cd momo-agents

# Create and activate a virtual environment
uv venv
source .venv/bin/activate   # Linux/macOS

# Install the project with dev dependencies
uv pip install -e ".[dev]"

# Install the Ollama extra (required for ollama_* agents)
uv pip install -e ".[ollama]"

# Run linter
ruff check .
ruff format .

# Run type checker
mypy scripts/

# Run the full pipeline (Claude backend — default)
./start-team.sh --workspace workspace/my-feature

# Run the full pipeline (Ollama backend)
./start-team.sh --workspace workspace/my-feature --agent-type ollama
./start-team.sh --workspace workspace/my-feature --agent-type ollama --ollama-host http://localhost:11434 --model-junior qwen2.5-coder --model-senior qwen2.5-coder

# Run an agent directly (Claude backend)
python scripts/claude_agents/claude_designer_agent.py
python scripts/claude_agents/claude_business_analyst_agent.py --design workspace/design/my-feature.new.md
python scripts/claude_agents/claude_project_initialiser_agent.py --design workspace/design/my-feature.new.md
python scripts/story_orchestrator.py
python scripts/claude_agents/claude_junior_coding_agent.py
python scripts/claude_agents/claude_senior_coding_agent.py
python scripts/claude_agents/claude_merger_agent.py

# Run an agent directly (Ollama backend — requires a running Ollama instance)
python scripts/ollama_agents/ollama_designer_agent.py --model qwen2.5-coder
python scripts/ollama_agents/ollama_business_analyst_agent.py --design workspace/design/my-feature.new.md
python scripts/ollama_agents/ollama_project_initialiser_agent.py --design workspace/design/my-feature.new.md
python scripts/ollama_agents/ollama_junior_coding_agent.py
python scripts/ollama_agents/ollama_senior_coding_agent.py
python scripts/ollama_agents/ollama_merger_agent.py
# Override host:  --ollama-host http://192.168.1.10:11434
# Override model: --model llama3.1

# Check pipeline status
./status.sh

# Reset
./reset-stories.sh          # stories only (keeps generated code)
./reset-team.sh             # full reset (wipes all artefacts)
```

## Git Workflow

- **Default branch**: `master` / `main`
- **Feature branches**: Use descriptive names, e.g. `feature/agent-loop`, `fix/retry-logic`
- **Commit messages**: Clear and concise, focused on *why* not *what*
- **Do not force-push** to `master`/`main`

## Code Conventions

### Python Style
- Follow **PEP 8** enforced via **Ruff**
- Use **type annotations** throughout; checked with **mypy**
- Prefer explicit over implicit; avoid magic
- Keep functions small and focused on a single responsibility

### Naming
- `snake_case` for variables, functions, and modules
- `PascalCase` for classes
- `UPPER_SNAKE_CASE` for constants
- Prefix private members with `_`

### Error Handling
- Raise specific exceptions, not bare `Exception`
- Validate at system boundaries (user input, external APIs); trust internal code
- Do not add error handling for scenarios that cannot occur

### Testing
- Use **pytest** for all tests
- Place tests in a `tests/` directory mirroring the source structure
- Aim for high coverage on core agent logic
- Use `pytest.mark.parametrize` for table-driven tests

## Ollama Agent Robustness

The Ollama backend uses two complementary mechanisms in `ollama_utilities.py` to handle models that do not always emit structured function calls:

- **Text-tool-call fallback** (`_try_extract_tool_calls_from_text`, `_handle_text_tool_calls`): When a model response contains no structured `tool_calls`, the response content is scanned for JSON objects (including code-fence-wrapped ones) that match known tool names. Matched calls are executed normally and appended to the message history.
- **Continuation prompts** (`continuation_prompt`, `max_continuations`): When `run_agent_loop` receives a text-only turn (after the fallback finds nothing), it re-prompts the model with a continuation message up to `max_continuations` times before returning. All task-oriented Ollama agents pass a `continuation_prompt`.

Ollama role files (`roles/ollama-*.md`) contain explicit per-tool documentation and call examples because local models do not reliably infer calling conventions from schema alone. When adding a new Ollama agent, create a dedicated `ollama-<role>.md` alongside the shared `<role>.md`.

The Ollama Merger Agent uses a minimal `MERGER_TOOLS` set (`bash` + `write_file`) defined inline in `ollama_merger_agent.py` rather than the shared `CODING_TOOLS`, since it only needs to run git commands and write the outcome file.

## Isolated Workspace Pipeline

Coding agents (Junior and Senior) no longer write directly to the shared workspace. The flow per story is:

1. **Python** (`copy_workspace_for_story`): copy the full workspace (excluding `.sentinels/`) into `.sentinels/STORY-NNN/`. The copy includes `stories/` and `design/` so the LLM can read context.
2. **LLM session**: the agent runs entirely inside the temp workspace. `cwd`, story path, and outcome file all point there.
3. **Post-session (Python)**:
   - `outcome == "done"` → `zip_workspace_for_merge` zips the temp workspace (excluding `.git/`, `stories/`, `design/`, and `.gitignore` patterns) into `.sentinels/merge-queue/STORY-NNN.zip`. The main workspace story stays in `.working.md`.
   - `outcome == "failed"` / no outcome → failure reasons are copied back to the main story file; `finalise_story` renames to `.failed.md` / `.ready.md` as before.
4. **Python**: temp workspace is deleted.

The **Merger Agent** then processes `merge-queue/` in ascending story-number order:
1. **Python** (`unzip_workspace_for_merge`): unzip to `.sentinels/merge-STORY-NNN/`.
2. **LLM**: create a git branch named `story-NNN`, `cp -r` staged files into the workspace, `git add -A`, commit, merge to `main`.
3. **Python** (`mark_story_done_after_merge`): rename `.working.md` → `.done.md` in `workspace/stories/`.
4. **Python**: delete staging dir and zip.

Key utility functions live in `scripts/agent_utilities.py`:
- `get_story_id(story_path)` — extracts `STORY-NNN` from any story filename
- `copy_workspace_for_story(workspace_dir, sentinels_dir, story_id)` — performs the copy
- `zip_workspace_for_merge(temp_workspace, story_id, merge_queue_dir)` — creates the zip
- `get_next_merge_story(merge_queue_dir)` — returns the lowest-numbered zip or `None`
- `unzip_workspace_for_merge(zip_path, sentinels_dir)` — extracts to staging dir
- `mark_story_done_after_merge(stories_dir, story_id, run_log, agent_name)` — renames to `.done.md`

The **Watchdog** skips `.working.md` files that have a corresponding `merge-queue/STORY-NNN.zip` — those are queued for the Merger and must not be reset to `.ready.md`.

## AI Agent Guidelines

When working in this repository as Claude Code or another AI assistant:

1. **Read before editing** — always read a file before modifying it
2. **Minimal changes** — only change what is necessary for the task; do not refactor unrelated code
3. **No speculative features** — do not add functionality that was not requested
4. **Update CLAUDE.md** — when project structure, conventions, or workflows change significantly, update this file to reflect the new state
5. **Check .gitignore** — do not commit virtual environments (`.venv/`, `venv/`, `env/`), build artifacts, or secrets (`.env`)
6. **Branch discipline** — develop on the designated feature branch; never push directly to `master`/`main` without confirmation
7. **Security** — never commit secrets, API keys, or credentials; use environment variables loaded from `.env` (excluded from git)

## Environment Variables

> No `.env.example` exists yet. Create one when secrets or configuration values are introduced.

Expected variables (update as the project evolves):

```env
ANTHROPIC_API_KEY=your_api_key_here
```

## Updating This File

This CLAUDE.md should be kept up to date as the project evolves. Update it when:
- The project structure changes significantly
- New tools or dependencies are added
- Development workflows are established
- Conventions are formalized or changed
