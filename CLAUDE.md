# CLAUDE.md

This file provides guidance for AI assistants (Claude Code and others) working in this repository.

## Project Overview

**momo-agents** is a Python project for building coding agents powered by the Claude Agent SDK. A team of specialised agents collaborate over the filesystem to take a feature idea from concept through to working, tested code.

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
├── scripts/                # Python agent and utility implementations
│   ├── designer_agent.py             # Interactive design session → workspace/design/<feature>.md
│   ├── business_analyst_agent.py     # Decomposes design into story files
│   ├── project_initialiser_agent.py  # Scaffolds workspace/ from design; writes workspace/CLAUDE.md
│   ├── story_orchestrator.py         # Non-LLM utility; marks stories ready when deps are met
│   ├── junior_coding_agent.py        # Claims and implements easy stories
│   ├── senior_coding_agent.py        # Claims and implements medium/hard stories
│   ├── story_reviewer_agent.py       # Triages failed stories with user
│   ├── agent_utilities.py            # Shared agent helpers
│   └── token_logger.py               # Shared JSONL token-usage logger
├── roles/                  # System prompt files (one per LLM agent)
│   ├── designer.md
│   ├── business-analyst.md
│   ├── project-initialiser.md
│   ├── junior-coding-agent.md
│   ├── senior-coding-agent.md
│   └── story-reviewer.md
├── workspace/              # All generated artefacts
│   ├── CLAUDE.md           # Build/test/lint instructions; start gate for all agents
│   ├── design/             # Designer Agent outputs (<feature>.new.md / <feature>.processed.md)
│   ├── stories/            # Story files (complexity + state encoded in filename)
│   ├── .sentinels/         # Runtime coordination files (created by start-team.sh)
│   ├── src/
│   └── tests/
├── start-team.sh           # Launches all agents simultaneously in named terminal windows
├── reset-team.sh           # Wipes all artefacts; resets to clean state
├── reset-stories.sh        # Resets story files only (keeps generated code)
├── status.sh               # Live story-state summary
└── watchdog.sh             # Resets stale .working.md files after 10 min
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

# Run linter
ruff check .
ruff format .

# Run type checker
mypy scripts/

# Run the full pipeline
./start-team.sh <feature-name>

# Run an agent directly
python scripts/designer_agent.py
python scripts/business_analyst_agent.py --design workspace/design/my-feature.new.md
python scripts/project_initialiser_agent.py --design workspace/design/my-feature.new.md
python scripts/story_orchestrator.py
python scripts/junior_coding_agent.py
python scripts/senior_coding_agent.py
python scripts/story_reviewer_agent.py

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
