# momo-agents

A multi-agent coding pipeline that takes a feature idea from concept through to working, tested code — without human intervention between steps. Supports two AI backends: the **Claude Agent SDK** (cloud) and a locally running **Ollama** instance (local/offline). Backends can be mixed freely: each agent role (Designer, Business Analyst, Project Initialiser, Junior Coder, Senior Coder, Merger) can be independently configured as either Claude or Ollama, letting you balance cost, speed, and capability per role.

Coding agents work in **isolated workspace copies** — each story is implemented in a private temp directory so parallel agents never touch each other's files. Completed workspaces are queued as zips and a dedicated **Merger Agent** commits and merges them into the shared workspace git repository in story order.

---

## Setup

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- **Claude backend**: an Anthropic API key
- **Ollama backend**: a running [Ollama](https://ollama.com) instance with at least one model pulled (e.g. `ollama pull qwen3.5:9b`)

### Install

```bash
# 1. Clone the repository
git clone https://github.com/bameschot/momo-agents.git
cd momo-agents

# 2. Create a virtual environment
uv venv
source .venv/bin/activate      # Linux / macOS

# 3. Install the project and its dependencies
uv pip install -e ".[dev]"

# 4a. Claude backend — add your API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env

# 4b. Ollama backend — install the extra and pull a model
uv pip install -e ".[ollama]"
ollama pull qwen3.5:9b
```

---

## Running the pipeline

### Start the full team

```bash
./start-team.sh --workspace <path> [options]
```

Opens every agent simultaneously in its own named terminal window and monitors the pipeline in the current terminal until you press **Ctrl+C**. Each agent window prints its **mode** and **model** at startup so you can confirm configuration at a glance.

`<path>` is the workspace directory where all generated artefacts live. It can be anywhere on the filesystem — inside or outside the `momo-agents` repo. If the directory does not exist, `start-team.sh` will offer to create it and initialise a git repository inside it. The script records the start time when the team launches so the shutdown step can export only the commits made during this run.

| Flag | Description | Default |
|---|---|---|
| `--workspace <path>` | Path to the workspace directory (required) | — |
| `--agent-type TYPE` | Global AI backend for all roles: `claude` or `ollama` | `claude` |
| `--designer-agent-type TYPE` | Backend override for the Designer | inherits `--agent-type` |
| `--ba-agent-type TYPE` | Backend override for the Business Analyst | inherits `--agent-type` |
| `--pi-agent-type TYPE` | Backend override for the Project Initialiser | inherits `--agent-type` |
| `--junior-agent-type TYPE` | Backend override for Junior Coding Agents | inherits `--agent-type` |
| `--senior-agent-type TYPE` | Backend override for Senior Coding Agents | inherits `--agent-type` |
| `--resolver-agent-type TYPE` | Backend override for Story Resolver Agent | inherits `--agent-type` |
| `--merger-agent-type TYPE` | Backend override for Merger Agent | inherits `--agent-type` |
| `--ollama-host URL` | Ollama API base URL (used by any role configured as ollama) | `http://localhost:11434` |
| `--junior-agents N` | Number of parallel Junior Coding Agents (easy stories) | `2` |
| `--senior-agents N` | Number of parallel Senior Coding Agents (medium/hard stories) | `1` |
| `--model-designer M` | Model for the Designer | see defaults below |
| `--model-ba M` | Model for the Business Analyst | see defaults below |
| `--model-pi M` | Model for the Project Initialiser | see defaults below |
| `--model-junior M` | Model for Junior Coding Agents | see defaults below |
| `--model-senior M` | Model for Senior Coding Agents | see defaults below |
| `--model-resolver M` | Model for Story Resolver Agent | see defaults below |
| `--model-merger M` | Model for Merger Agent | see defaults below |

**Model defaults** (each role uses the default for its own configured backend):

| Agent | claude default | ollama default |
|---|---|---|
| Designer | `claude-sonnet-4-6` | `qwen3.5:4b` |
| Business Analyst | `claude-sonnet-4-6` | `qwen3.5:4b` |
| Project Initialiser | `claude-haiku-4-5-20251001` | `qwen3.5:4b` |
| Junior Coding Agent | `claude-haiku-4-5-20251001` | `qwen3.5:4b` |
| Senior Coding Agent | `claude-sonnet-4-6` | `qwen3.5:4b` |
| Story Resolver | `claude-sonnet-4-6` | `qwen3.5:4b` |
| Merger Agent | `claude-haiku-4-5-20251001` | `qwen3.5:4b` |

**Claude effort levels** (only applied when a role's agent type is `claude`):

| Flag | Role | Default |
|---|---|---|
| `--designer-claude-effort E` | Designer | `medium` |
| `--ba-claude-effort E` | Business Analyst | `medium` |
| `--pi-claude-effort E` | Project Initialiser | `medium` |
| `--junior-claude-effort E` | Junior Coding Agents | `medium` |
| `--senior-claude-effort E` | Senior Coding Agents | `medium` |
| `--resolver-claude-effort E` | Story Resolver Agent | `medium` |
| `--merger-claude-effort E` | Merger Agent | `medium` |

Valid values: `low`, `medium`, `high`, `max`. Effort controls how much thinking Claude does per turn — higher effort trades speed and cost for quality. Ollama roles ignore these flags.

**Agent windows opened:**

| Window | Agent | Notes |
|---|---|---|
| `🎨 Designer Agent` | Interactive design session | Type requirements; `write` saves the design |
| `🏗️ Project Initialiser` | Workspace scaffolder | Runs once; skips if workspace already populated |
| `📋 Business Analyst` | Design watcher | Polls `<workspace>/design/` every 5 s; waits for `<workspace>/CLAUDE.md` |
| `🎯 Story Orchestrator` | Readiness manager | Continuously marks stories ready as deps complete |
| `🐕 Watchdog` | Stale story reset | Resets stories idle > 10 min back to `.ready.md` |
| `🟢 Junior Coding Agent N` | Easy story implementation | Works in an isolated workspace copy; queues result to `merge-queue/` on success |
| `🔵 Senior Coding Agent N` | Medium/hard story implementation | Works in an isolated workspace copy; queues result to `merge-queue/` on success |
| `🔀 Merger Agent` | Git branch + merge for completed stories | Polls `merge-queue/`; merges story zips into the workspace git repo in story order |
| `🔧 Story Resolver` | Interactive failed-story triage | Polls for `*.failed.md`; prompts you to resolve each one interactively |

**Examples:**

```bash
# Claude backend — 2 junior agents, 1 senior agent (defaults)
./start-team.sh --workspace /path/to/my-project

# Ollama backend — all agents use local qwen3.5:9b (simplest config)
./start-team.sh --workspace /path/to/my-project --agent-type ollama

# Ollama — recommended per-role model split for best results
./start-team.sh --workspace /path/to/my-project \
  --agent-type ollama \
  --model-junior   qwen3.5:9b  \
  --model-senior   qwen3.5:9b \
  --model-pi       qwen3.5:9b \
  --model-ba       qwen2.5:7b

# Ollama on a remote host
./start-team.sh --workspace /path/to/my-project \
  --agent-type ollama \
  --ollama-host http://192.168.1.10:11434

# Relative paths are resolved from the current directory
./start-team.sh --workspace ../my-project

# Scale up for a large backlog
./start-team.sh --workspace /path/to/my-project --junior-agents 4 --senior-agents 2

# Use a different model for design only (Claude)
./start-team.sh --workspace /path/to/my-project --model-designer claude-opus-4-6

# Raise effort for coding agents to maximise code quality
./start-team.sh --workspace /path/to/my-project \
  --junior-claude-effort high \
  --senior-claude-effort high

# Lower effort on mechanical roles to reduce cost, keep high effort where it matters
./start-team.sh --workspace /path/to/my-project \
  --ba-claude-effort low \
  --pi-claude-effort low \
  --merger-claude-effort low \
  --junior-claude-effort high \
  --senior-claude-effort high

# Max effort on senior agent only (complex stories)
./start-team.sh --workspace /path/to/my-project --senior-claude-effort max
```

### Hybrid mode — mixing Claude and Ollama per role

Each agent role can be configured independently as either `claude` or `ollama`. Use `--agent-type` to set the global default and then override individual roles with the per-role flags. This lets you use cloud models where quality matters most and local models where speed or cost is the priority.

Per-role flags: `--designer-agent-type`, `--ba-agent-type`, `--pi-agent-type`, `--junior-agent-type`, `--senior-agent-type`, `--merger-agent-type`. Each accepts `claude` or `ollama` and defaults to `--agent-type` when not set.

Each role's model default is derived from its own configured backend, so you only need to pass `--model-<role>` when you want to override the default for that backend.

```bash
# Claude for design and planning; Ollama for the high-volume coding work
./start-team.sh --workspace /path/to/my-project \
  --agent-type claude \
  --junior-agent-type ollama  --model-junior qwen3.5:9b \
  --senior-agent-type ollama  --model-senior qwen2.5-coder:14b

# Fully local except for the Senior Coding Agent (most complex stories)
./start-team.sh --workspace /path/to/my-project \
  --agent-type ollama \
  --senior-agent-type claude

# Claude for interactive/creative roles; Ollama for mechanical decomposition
./start-team.sh --workspace /path/to/my-project \
  --agent-type claude \
  --ba-agent-type ollama  --model-ba qwen2.5:7b \
  --pi-agent-type ollama  --model-pi qwen3.5:9b

# All Ollama with a stronger model for senior stories
./start-team.sh --workspace /path/to/my-project \
  --agent-type ollama \
  --model-junior qwen3.5:9b \
  --model-senior qwen2.5-coder:14b
```

### Monitor progress

```bash
./status.sh
```

Prints a live snapshot of how many stories are in each state:

```
  unprocessed    2   STORY-001.md  STORY-004.md          (workspace/stories/)
  ready          1   STORY-002.easy.ready.md              (.sentinels/story-orchestrator/)
  working        1   STORY-003.medium.working.md          (.sentinels/story-orchestrator/)
  done           3   STORY-005.done.md  ...               (workspace/stories/, committed)
  failed         0
```

### Shut down

Press **Ctrl+C** in the `start-team.sh` terminal. This:

1. Writes `<workspace>/.sentinels/pipeline_complete` — all agent windows exit cleanly.
2. Kills the watchdog process and closes all opened agent terminal windows.
3. Prints a final per-agent token-usage summary and `status.sh` snapshot.
4. Exports the git commit log of the workspace for the run (commits since the team started) to `<workspace>/.sentinels/git_log.jsonl` using `git_log_exporter.py`.
5. Generates a self-contained HTML run report and writes it to `<workspace>/run-report_YYYY-MM-DD_HH-MM-SS.html`.
6. Removes the `<workspace>/.sentinels/` directory.

The run report (generated by `run_report.py`) contains three sections:
- **Run Log** — every pipeline event recorded by agents (design written, project initiated, story created, story done/failed), ordered chronologically.
- **Git Commits** — every commit made to the workspace repository during the run, sourced from `git_log.jsonl`.
- **Token Usage** — per-agent breakdown of input, output, and cache tokens plus cost, with an interactive Chart.js timeline.

Open it in any browser after the run.

### Reset

**Reset stories only** (keep generated code):

```bash
rm -f <workspace>/stories/STORY-*.md
```

**Full reset** — wipe everything generated:

```bash
./reset-team.sh        # interactive — asks for confirmation
./reset-team.sh --yes  # non-interactive
```

| Path | What gets deleted |
|---|---|
| `<workspace>/stories/` | All `STORY-*` files in every state |
| `<workspace>/design/` | All `*.md` design documents |
| `<workspace>/.sentinels/` | Entire directory (wrapper scripts, tokens, sentinels) |
| `<workspace>/` | All generated source code, tests, `CLAUDE.md`, and build artefacts |

After a full reset, re-running `./start-team.sh --workspace <path>` goes through the complete pipeline from scratch.

---

## Pipeline overview

```
  You ──► Designer ──► Project Initialiser
                              │
                    writes <workspace>/CLAUDE.md
                              │
               ┌──────────────┴──────────────────────┐
               ▼                                     ▼
     Business Analyst                       Story Orchestrator
    (waits for CLAUDE.md,                  (marks stories ready
     then decomposes design)                when deps are met)
               │                                     │
               └──────────────┬──────────────────────┘
                              ▼
             (waits for <workspace>/CLAUDE.md)
               ┌──────────────┴──────────────┐
               ▼                             ▼
     Junior Coding Agent 1 ──┐   Senior Coding Agent 1 ──┐
     Junior Coding Agent 2 ──┤   Senior Coding Agent 2 ──┤
           [easy]            │         [medium/hard]      │
                             │  each works in an isolated │
                             │  copy of the workspace     │
                             └──────────┬────────────────-┘
                                        │ success → STORY-NNN.zip
                                        ▼
                              .sentinels/merge-queue/
                                        │ (in story order)
                                        ▼
                                 Merger Agent
                          (git branch from base commit →
                           copy → commit → 3-way merge
                           into main → mark done)
                                        │ (on failure)
                                        ▼
                               *.failed.md stories
                                        │
                                        ▼
                               Story Resolver ◄── You
                              (interactive; fix &
                               reset to *.ready.md)
```

The pipeline has one hard sequencing constraint: the **Project Initialiser** runs first and writes `CLAUDE.md` at the workspace root. The **Business Analyst** and all **Coding Agents** poll for this file and will not start work until it exists. Everything else is coordinated via atomic filesystem operations — no agent explicitly waits for another.

**Story state locations** — live runtime state (`.ready.md`, `.working.md`, `.failed.md`) is tracked in `.sentinels/story-orchestrator/`, which is never touched by git. Source stories (`STORY-NNN.md`) and committed done markers (`STORY-NNN.done.md`) live in `workspace/stories/`. This separation means git merges by the Merger Agent never conflict with story state files.

| Agent | Role | Reads from | Writes to |
|---|---|---|---|
| **Designer** | Multi-turn interactive Q&A with user; writes design on `write` command | User input (terminal) | `<workspace>/design/` |
| **Project Initialiser** | Reads the design, determines the correct tech-stack scaffolding, and writes `CLAUDE.md` at the workspace root; all other agents gate on this file | `<workspace>/design/` | `<workspace>/` |
| **Business Analyst** | Waits for `CLAUDE.md`, then decomposes the design into story files | `<workspace>/design/*.new.md`, `<workspace>/CLAUDE.md` | `<workspace>/stories/STORY-NNN.md` |
| **Story Orchestrator** | Plain Python utility (no LLM); watches `<workspace>/stories/` for bare `STORY-NNN.md` files, parses complexity and deps, **copies** to `.sentinels/story-orchestrator/STORY-NNN.[complexity].ready.md` when deps are met; skips stories already present in the orchestrator dir | `<workspace>/stories/STORY-NNN.md`, `<workspace>/stories/*.done.md` | `.sentinels/story-orchestrator/` |
| **Junior Coding Agent** (×N) | Claims one `easy` story at a time from the orchestrator dir; **copies the workspace** into an isolated temp dir (recording git HEAD as `.merge-base-commit` for a correct 3-way merge); also copies the story file into the temp workspace so the LLM can read it; works entirely in isolation; on success zips the temp workspace into `merge-queue/` (**always excluding `stories/`, `design/`, `.git/`, and `.gitignore`-matched paths**) — story stays `.working.md` in the orchestrator dir until the Merger promotes it; on failure copies failure reasons back and marks the story `.failed.md` in the orchestrator dir | `.sentinels/story-orchestrator/*.easy.ready.md`, `<workspace>/CLAUDE.md` | `.sentinels/merge-queue/STORY-NNN.zip` (success) or `.sentinels/story-orchestrator/*.failed.md` (failure) |
| **Senior Coding Agent** (×N) | Claims one `medium`/`hard` story at a time from the orchestrator dir; same isolated-workspace flow as Junior Coding Agent | `.sentinels/story-orchestrator/*.medium/hard.ready.md`, `<workspace>/CLAUDE.md` | `.sentinels/merge-queue/STORY-NNN.zip` (success) or `.sentinels/story-orchestrator/*.failed.md` (failure) |
| **Merger Agent** | Polls `merge-queue/` in ascending story-number order; for each zip: unzips to a staging dir, asks the LLM to create a git branch **from the base commit recorded at workspace-copy time**, copy the staged files (**never `stories/` or `design/`** — skip unconditionally even if present), commit, and merge back to `main` via a 3-way merge; then renames `workspace/stories/STORY-NNN.md` → `STORY-NNN.done.md`, **commits that rename to git** (for restart resilience), removes the orchestrator dir entry, and deletes the staging dir | `.sentinels/merge-queue/STORY-NNN.zip` | `<workspace>/` (git commits), `<workspace>/stories/*.done.md` (committed) |
| **Watchdog** | Resets stale `.working.md` files whose agent has died or stalled (idle > 10 min) back to `.ready.md`; **skips stories already in `merge-queue/`** — those are awaiting the Merger Agent and must not be reset | `.sentinels/story-orchestrator/`, `.sentinels/merge-queue/` | `.sentinels/story-orchestrator/` |
| **Story Resolver** | Interactive; polls the orchestrator dir for `*.failed.md` stories; when found, opens a conversation to diagnose the failure, propose fixes, and reset the story to `*.ready.md` in the orchestrator dir | `.sentinels/story-orchestrator/*.failed.md`, `<workspace>/` (read-only for context) | `.sentinels/story-orchestrator/*.failed.md` (edits then renames to `*.ready.md`) |

Each LLM agent reads its system prompt from the corresponding file in `roles/` at startup. `story_orchestrator.py` makes no LLM calls.

### Story failure reasons

When a coding agent cannot complete a story it appends a `## Failure Reasons` section to the story file before the pipeline harness renames it to `.failed.md`. The section contains a concise human- and machine-readable summary of what went wrong — failed test names, lint errors, and a brief description of what was attempted.

```markdown
## Failure Reasons

- `pytest tests/test_foo.py` failed: `AssertionError: expected 42, got None` in `test_bar`
- Linter reported 3 errors in `src/foo.py` (unused import, type mismatch)
- Root cause: the `Bar` dependency was not yet implemented; story may have an unresolved dependency
```

This section is written to the story file in the isolated temp workspace. After the session the failure reasons are copied back to the `.working.md` entry in `.sentinels/story-orchestrator/`, which is then renamed to `.failed.md`. The section is readable by any subsequent agent or developer inspecting the failure without needing to dig through logs.

### Story Resolver Agent

The **Story Resolver** (`scripts/claude_agents/claude_story_resolver_agent.py`) runs alongside the team and polls `.sentinels/story-orchestrator/` for `.failed.md` stories. When one is found it opens an interactive Claude session directly in your terminal:

1. The agent reads the story (including `## Failure Reasons`) and presents the failure clearly.
2. You discuss the root cause — the agent can read workspace source files, tests, and `CLAUDE.md` for context.
3. You agree on a resolution: correct an acceptance criterion, fix a wrong assumption, clarify scope, etc.
4. When you are satisfied, tell the agent **"update the story"**. Claude:
   - Removes the `## Failure Reasons` section from the story.
   - Applies any agreed changes to the acceptance criteria or other sections.
   - Writes a `resolved` sentinel to signal the Python harness.
5. The Python harness renames the story from `.failed.md` back to `.ready.md` so a coding agent picks it up again.

**Session commands:**

| Command | Effect |
|---|---|
| `update the story` | Apply agreed fixes and reset the story to ready |
| `skip` | Leave this story as `.failed.md` and scan for the next |
| `exit` | Stop the resolver |

Both Claude and Ollama backends are supported. The Ollama resolver uses the `ask_user` tool (see [Ollama agent tools](#ollama-agent-tools)) instead of raw `input()` calls, so the model controls all user interaction — it asks questions, presents findings, and confirms before writing changes. Override the backend with `--resolver-agent-type` and the model with `--model-resolver`.

---

## AI backends

### Claude (default)

Uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk). Requires an Anthropic API key. Each agent script lives in `scripts/claude_agents/`.

### Ollama (local)

Uses a locally running [Ollama](https://ollama.com) instance. No API key required — models run entirely on your machine. Each agent script lives in `scripts/ollama_agents/` and shares common tool infrastructure from `scripts/ollama_agents/ollama_utilities.py`.

The Ollama agents implement their own agentic tool-call loop (`run_agent_loop` in `ollama_utilities.py`) using the OpenAI function-call format. See [Ollama agent tools](#ollama-agent-tools) for the full tool reference and per-agent availability.

**Robustness features** — `ollama_utilities.py` implements two mechanisms to cope with common local-model failure modes:

- **Text-embedded tool call detection**: some models output tool call JSON as plain text rather than using the structured function-call mechanism. Both `run_agent_loop` and `run_chat_loop` scan every text-only response for JSON objects matching a known tool name, execute any found, and feed the results back to the model — exactly as if a structured call had been made.
- **Continuation prompts**: models sometimes emit a text-only planning turn between steps (e.g. after reading a design document, before writing files). When no tool call — structured or text-embedded — is found, the agent loop re-prompts the model with a task-specific continuation message rather than exiting prematurely. Up to three consecutive text-only turns are tolerated before the loop accepts the response as a genuine completion.

**Recommended models** (reliable tool calling is the critical factor):

| Tier | Model | Best for |
|---|---|---|
| Best overall | `qwen2.5-coder:14b` | Senior agent, Project Initialiser |
| Good, faster | `qwen3.5:9b` | Junior agent |
| Better prose | `qwen2.5:14b` | Business Analyst |
| Strong code | `codestral:22b` | Senior agent (less consistent tool calling) |
| Compact reasoning | `phi4:14b` | BA alternative |

---

## Ollama agent tools

Each Ollama agent is given a fixed set of tools at startup. All tool implementations live in `scripts/ollama_agents/ollama_utilities.py` and are dispatched by a shared `ToolExecutor`.

### Tool availability by agent

| Tool | Designer | Business Analyst | Project Initialiser | Junior Coding | Senior Coding | Merger | Story Resolver |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| `read_file` | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ |
| `write_file` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `edit_file` | | | ✓ | ✓ | ✓ | | ✓ |
| `bash` | | ✓ | ✓ | ✓ | ✓ | ✓ | |
| `glob` | ✓ | ✓ | ✓ | ✓ | ✓ | | ✓ |
| `grep` | | | ✓ | ✓ | ✓ | | ✓ |
| `ask_user` | | | | | | | ✓ |

The tools are grouped into named collections in `ollama_utilities.py`:

| Collection | Tools | Used by |
|---|---|---|
| `DESIGNER_TOOLS` | `read_file`, `write_file`, `glob` | Designer |
| `ANALYST_TOOLS` | `read_file`, `write_file`, `glob` | *(base set; not used directly)* |
| `BA_TOOLS` | `read_file`, `write_file`, `glob`, `bash` | Business Analyst |
| `CODING_TOOLS` | `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep` | Project Initialiser, Junior Coding, Senior Coding |
| `MERGER_TOOLS` | `bash`, `write_file` | Merger |
| `RESOLVER_TOOLS` | `read_file`, `write_file`, `edit_file`, `glob`, `grep`, `ask_user` | Story Resolver |

### Tool reference

#### `read_file`
Read the full text content of a file from disk.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `path` | string | ✓ | Absolute or working-directory-relative path to the file |

Returns the file content as a string, or an error message if the file does not exist or cannot be read. Used by every agent to inspect design documents, story files, generated source code, and workspace metadata.

---

#### `write_file`
Write (or completely overwrite) a file with new content.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `path` | string | ✓ | Destination file path (absolute or relative) |
| `content` | string | ✓ | Full content to write |

Parent directories are created automatically. Returns a success or error message. Used by the Designer to save design documents, by the Business Analyst to write story files, and by coding agents to create or replace source and test files.

---

#### `edit_file`
Replace the **first occurrence** of an exact string inside an existing file.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `path` | string | ✓ | Path to the file to modify |
| `old_string` | string | ✓ | Exact text to find (must match byte-for-byte, including whitespace) |
| `new_string` | string | ✓ | Replacement text |

Returns an error if `old_string` is not found, making the operation safe to use without a full rewrite. Agents are expected to `read_file` first so the match string is exact. Used by coding agents to make surgical edits to existing source files rather than rewriting them wholesale.

---

#### `bash`
Execute a shell command in the agent's working directory and return its output.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `command` | string | ✓ | Shell command to run — must be a plain POSIX shell string; never nest tool-call syntax inside this value |

Runs via `subprocess.run()` with a **120-second timeout**. Returns the combined stdout and stderr. The working directory is set to the workspace root automatically — no `cd` prefix is needed. Used by coding agents to run build tools, test runners, and linters.

---

#### `glob`
Find files matching a glob pattern, returning their absolute paths.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `pattern` | string | ✓ | Glob pattern, e.g. `src/**/*.py` or `stories/*.ready.md` |
| `directory` | string | | Root directory to search from (default: working directory) |

Returns a newline-separated, sorted list of absolute paths. Recursive patterns (`**`) are supported. Used by all agents to discover design files, story files, and source files without having to know exact names ahead of time.

---

#### `grep`
Search file contents for a regular expression, returning matching lines with file paths and line numbers.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `pattern` | string | ✓ | Regular expression to search for |
| `path` | string | | File or directory to search (default: working directory) |
| `glob` | string | | Restrict search to files matching this glob, e.g. `*.py` |

Used by coding agents and the Project Initialiser to locate definitions, imports, usages, or configuration values across the workspace without reading every file individually.

---

#### `ask_user`
Display a message or question to the user and return their typed response. The call blocks until the user submits input.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `question` | string | ✓ | The message or question to display |

Returns the user's response as a string. If the user types `skip`, raises `UserSkipRequest` (bubbles up through the agent loop, causing the resolver to skip the current story). If the user types `exit` or `quit`, or sends EOF/Ctrl-C, raises `UserExitRequest` (stops the resolver). Used exclusively by the Story Resolver to drive the interactive triage conversation — it replaces the alternating `input()` loop used by the Claude resolver and gives the model full control over when to prompt, what to ask, and in what order.

---

## Repository layout

```
momo-agents/
├── scripts/
│   ├── agent_utilities.py         ← shared helpers (path utils, run-log, workspace copy/zip/merge)
│   ├── token_logger.py            ← shared JSONL token-usage logger and console printer
│   ├── story_orchestrator.py      ← non-LLM; shared by all agent types; marks stories ready
│   ├── git_log_exporter.py        ← exports workspace git log to JSONL for the run report
│   ├── run_report.py              ← generates the HTML run report (run log + git commits + token usage)
│   ├── claude_agents/             ← agents backed by the Claude Agent SDK
│   │   ├── claude_designer_agent.py
│   │   ├── claude_business_analyst_agent.py
│   │   ├── claude_project_initialiser_agent.py
│   │   ├── claude_junior_coding_agent.py      ← claims easy stories; isolated workspace flow
│   │   ├── claude_senior_coding_agent.py      ← claims medium/hard stories; isolated workspace flow
│   │   └── claude_merger_agent.py             ← merges story zips into main branch
│   └── ollama_agents/             ← agents backed by a local Ollama instance
│       ├── ollama_utilities.py            ← shared tool defs, ToolExecutor, agent loops, text-tool-call fallback
│       ├── ollama_designer_agent.py
│       ├── ollama_business_analyst_agent.py
│       ├── ollama_project_initialiser_agent.py
│       ├── ollama_junior_coding_agent.py      ← isolated workspace flow
│       ├── ollama_senior_coding_agent.py      ← isolated workspace flow
│       └── ollama_merger_agent.py             ← merges story zips into main branch
├── roles/                     ← system prompt files (one per LLM agent)
│   ├── claude_roles/                  ← prompts for the Claude backend
│   │   ├── claude_designer.md
│   │   ├── claude_business-analyst.md
│   │   ├── claude_project-initialiser.md
│   │   ├── claude_junior-coding-agent.md
│   │   ├── claude_senior-coding-agent.md
│   │   └── claude_merger-agent.md
│   └── ollama_roles/                  ← prompts for the Ollama backend
│       ├── ollama-designer.md
│       ├── ollama-business-analyst.md
│       ├── ollama-project-initialiser.md
│       ├── ollama-junior-coding-agent.md
│       ├── ollama-senior-coding-agent.md
│       └── ollama-merger-agent.md
├── start-team.sh              ← launches all agents simultaneously
├── reset-team.sh              ← wipes all artefacts; resets to clean state
├── status.sh                  ← live story-state summary
└── watchdog.sh                ← resets stale .working.md files; skips merge-queued stories
```

---

## Workspace layout

The workspace is a **separate directory** that lives outside the `momo-agents` repo — pass it to `--workspace` when starting the team. It can be anywhere on your filesystem; `start-team.sh` will create it and initialise a git repository inside it if it does not already exist.

All pipeline artefacts are written here. Nothing inside `momo-agents/` itself is modified during a run.

```
<workspace>/                   ← root of the generated project (any path you choose)
├── CLAUDE.md                  ← build/test/lint instructions written by the Project Initialiser;
│                                 acts as the start gate for the Business Analyst and all Coding Agents
├── design/                    ← Designer Agent outputs
│   ├── <feature>.new.md           ← written by the Designer; queued for the Business Analyst
│   └── <feature>.processed.md     ← renamed by the BA after stories are generated
├── stories/                   ← story files; complexity and state are encoded in the filename
│   ├── STORY-001.md                       ← unprocessed (just written by BA, awaiting orchestrator)
│   ├── STORY-002.easy.ready.md            ← deps met; ready for a Junior Coding Agent
│   ├── STORY-003.medium.working.md        ← claimed by a Senior Coding Agent
│   ├── STORY-004.easy.done.md             ← implementation complete
│   └── STORY-005.hard.failed.md           ← implementation failed
├── .sentinels/                ← runtime coordination files created by start-team.sh;
│   │                             entire directory is removed on clean shutdown
│   ├── pipeline_complete          ← written on Ctrl+C; signals all agents to exit
│   ├── config.sh                  ← shared environment variables sourced by wrapper scripts
│   ├── run-log.jsonl              ← pipeline event log (one JSON object per line)
│   ├── git_log.jsonl              ← workspace git commits for this run (exported on shutdown)
│   ├── STORY-NNN/                 ← isolated temp workspace for a coding agent working on STORY-NNN;
│   │                                 full copy of <workspace> (excluding .sentinels);
│   │                                 deleted after the agent finishes
│   ├── merge-queue/               ← zipped temp workspaces waiting to be merged by the Merger Agent
│   │   └── STORY-NNN.zip              ← created by coding agent on success; always excludes stories/, design/, .git/,
│   │                                     and .gitignore-matched paths; deleted by Merger after merge
│   ├── merge-STORY-NNN/           ← staging dir where Merger unzips a story before git operations;
│   │                                 deleted after merge completes
│   ├── merge-STORY-NNN.outcome    ← outcome sentinel written by the Merger LLM ('done' or 'failed');
│   │                                 deleted after use
│   ├── tokens/                    ← per-agent JSONL token-usage logs
│   └── run_*.sh                   ← per-agent wrapper scripts
├── src/                       ← generated application source code
├── tests/                     ← generated tests
└── run-report_YYYY-MM-DD_HH-MM-SS.html   ← self-contained HTML run report (written on shutdown)
```

### Story filename convention

Story state and complexity are encoded directly in the filename so agents can claim work with a single atomic rename — no database or lock file required.

```
STORY-NNN.<complexity>.<state>.md
```

| Segment | Values | Set by |
|---|---|---|
| `complexity` | `easy`, `medium`, `hard` | Business Analyst (when writing the story) |
| `state` | *(none)* → `ready` → `working` → `done` \| `failed` | Story Orchestrator (`ready`); Coding Agents (`working`, `failed`); Merger Agent (`done` only) |

A bare `STORY-NNN.md` (no complexity or state suffix) is newly written by the BA and not yet evaluated. The Story Orchestrator renames it to `STORY-NNN.<complexity>.ready.md` once all dependency stories are in `done` state.

> **State ownership rule**: only the Merger Agent may transition a story to `.done.md`. A Coding Agent that completes a story successfully leaves it in `.working.md` and places its zipped workspace in `merge-queue/`. The story advances to `.done.md` only after the Merger Agent has successfully committed and merged it into the main branch.

---

## Agent details

### Designer

The Designer runs as a multi-turn conversation. A **single LLM session persists for the entire interaction**, preserving full context across all turns.

**Python control flow**:
1. Creates `<workspace>/design/` if it does not exist.
2. Sends an initial system prompt to the model instructing it to greet the user and start the design session.
3. Enters a **Python read loop** — reads one line of user input at a time and sends it to the same open LLM session.
4. Exits the loop on `exit`, `quit`, `bye` (or `done` when using the Ollama backend), or **Ctrl+C**.

**LLM session behaviour**:
1. Greets the user and asks what they want to build.
2. Asks clarifying questions — technology stack, constraints, integrations, non-functional requirements — until it has a complete, unambiguous picture.
3. Does **not** write any files until the user types **`write`**.
4. On `write`: produces a thorough design document and saves it to `<workspace>/design/<feature-name>.new.md`, immediately queuing it for the Business Analyst.
5. After saving, it informs the user and invites further refinement. Typing `write` again overwrites the file and re-queues the design.
6. If a `<feature>.processed.md` already exists for the same feature, writing a new `.new.md` signals the BA to re-process the updated design.

---

### Project Initialiser

A **one-shot agent** invoked by `start-team.sh` when a new design file appears and `CLAUDE.md` does not yet exist in the workspace. Its primary output — `CLAUDE.md` at the workspace root — is the **start gate** for the Business Analyst and all Coding Agents. If `CLAUDE.md` already exists, `start-team.sh` skips launching the agent entirely.

**Python control flow**:
1. Validates the design file path passed via `--design`; exits with an error if not found.
2. Starts a single LLM session (`cwd` set to the workspace root) and exits when it completes.

**LLM session behaviour**:
1. Reads the design document in full.
2. Creates `CLAUDE.md` **at the workspace root** with precise, runnable build, test, and lint commands for the technology stack described in the design, including an **Agent Exclusion List** section.
3. Scaffolds the idiomatic directory layout, configuration files, and empty entry points for that stack.
4. Does **not** implement any story logic — only the skeleton that lets Coding Agents start immediately.

The agent's working directory is the workspace root; all paths are relative to it. `CLAUDE.md` is written directly at the root — never inside a subdirectory.

---

### Business Analyst

A **one-shot agent** — `start-team.sh` invokes it once per design file when a new `*.new.md` appears in `<workspace>/design/`. The BA processes exactly the design file passed via `--design` and then exits. The watch loop for new design files lives in `start-team.sh`, not in this script.

**Python control flow**:
1. Validates the design file path; exits with an error if not found.
2. Polls every 10 seconds until `<workspace>/CLAUDE.md` exists — ensures stories are written with full knowledge of the tech stack.
3. Creates `<workspace>/stories/` if it does not exist; counts existing `STORY-*.md` files to determine the next story number.
4. Starts a single LLM session and waits for completion.
5. After the session: renames `<feature>.new.md` → `<feature>.processed.md` inside `<workspace>/design/`.

**LLM session behaviour**:
1. Reads the design document in full.
2. Decomposes it into an ordered set of discrete, implementable stories.
3. Writes all `<workspace>/stories/STORY-NNN.md` files (bare, unprocessed — awaiting the Story Orchestrator) directly in the workspace.
4. Does not leave open questions — resolves ambiguities from the design before writing.

Each story includes a `**Complexity**: easy | medium | hard` field and a `**Depends on**` field. The BA **strongly prefers easy and medium stories** and only uses hard when splitting would produce incoherent or non-implementable units of work.

| Complexity | Effort | Meaning |
|---|---|---|
| **easy** | ~3 hours | Self-contained work with clear scope — a new module, a small integration, or several related changes within one subsystem |
| **medium** | ~6 hours | Multiple moving parts or significant design judgement — a feature spanning a few subsystems, a non-trivial algorithm, or a meaningful refactor |
| **hard** | > 6 hours | Broad cross-cutting changes, subtle concurrency/state management, or refactoring across many modules with unclear boundaries |

| Filename | State | Meaning |
|---|---|---|
| `<workspace>/design/<feature>.new.md` | **new** | Queued for BA; not yet processed |
| `<workspace>/design/<feature>.processed.md` | **processed** | Stories have been generated for this version |

---

### Story Orchestrator

A **plain Python utility** (no LLM calls) that continuously watches `<workspace>/stories/` and manages the unprocessed → ready transition.

**Python control flow** (continuous loop, exits on `pipeline_complete` sentinel):
1. Scans for bare `STORY-NNN.md` files written by the BA.
2. For each file: parses `**Complexity**` and `**Depends on**` fields.
3. Checks whether all listed dependencies have a corresponding `.done.md` file.
4. If complexity is valid and all deps are done (or there are no deps): renames `STORY-NNN.md` → `STORY-NNN.[complexity].ready.md`.
5. If deps are unmet or complexity is missing: logs the blocked story and re-checks on the next poll.
6. Sleeps for the poll interval, then repeats.

Decoupling dependency resolution from the coding agents keeps the agents simple and enables automatic unblocking — when a story finishes, the orchestrator immediately marks any dependent stories as ready without any agent needing to be aware.

Default poll interval: 5 seconds (configurable via `--poll-interval`).

---

### Coding Agents

Two tiers handle stories by complexity:

| Agent | Handles | Claude default model | Ollama default model |
|---|---|---|---|
| **Junior Coding Agent** | `easy` stories | `claude-haiku-4-5-20251001` | `qwen3.5:9b` |
| **Senior Coding Agent** | `medium` and `hard` stories | `claude-sonnet-4-6` | `qwen3.5:9b` |

Both agents follow the same structure: **Python owns the outer loop; a fresh LLM session is started for every story.** This keeps each session's context small and avoids the quadratic token cost that accumulates when tool-call history from previous stories remains in context.

**Python startup** (once, before the loop):
1. Poll every 10 s until `<workspace>/CLAUDE.md` exists.

**Python outer loop**:
1. Check for `<workspace>/.sentinels/pipeline_complete` — exit if it exists.
2. Atomically claim the lowest-numbered `.ready.md` story of the correct complexity tier by renaming it to `.working.md`. POSIX `rename(2)` is atomic — if two agents race, exactly one succeeds; the other moves to the next candidate.
3. If no story can be claimed, sleep 10 s and retry.
4. Determine the **outcome sentinel path**: `<workspace>/.sentinels/STORY-NNN.outcome`.
5. Start a **fresh LLM session** for the claimed story, passing the story path, workspace root, and outcome sentinel path in the task prompt.
6. After the session ends: read the outcome sentinel written by the LLM and **rename the story file in Python** accordingly (`.working.md` → `.done.md` or `.failed.md`), then delete the sentinel. Loop back to step 1.

**Per-story LLM session**:
1. Read `<workspace>/CLAUDE.md` — note build/test/lint commands and the Agent Exclusion List (never read from or write to those paths).
2. Read the story file and design document(s) from the story's **Design ref** field.
3. Implement the acceptance criteria in `<workspace>/`.
4. Run tests and linter as instructed in `CLAUDE.md`. Fix all failures.
5. **On success**:
   - Write `done` to the outcome sentinel file.
   - Stop immediately — do not perform any further tool calls.
   - Python then zips the temp workspace into `merge-queue/`, **always excluding `stories/`, `design/`, `.git/`, and `.gitignore`-matched paths** — these must never be committed to the main workspace.
6. **On failure**: write `failed` to the outcome sentinel file, then stop immediately.

The LLM session **never renames, writes, or deletes story files**. Story file state transitions always happen in Python after the LLM session returns.

**Outcome sentinel behaviour**: if the LLM session ends without writing an outcome, Python resets the story to `.ready.md` so another agent can retry it.

> `<workspace>/CLAUDE.md` is read at the start of every story session rather than being pre-loaded and injected into the task prompt. This keeps each session's initial context lean — for real projects CLAUDE.md can be several hundred lines — and avoids inflating input token costs across a large story backlog.

---

### Watchdog

Runs continuously alongside the Coding Agents. Every 60 seconds it scans `workspace/stories/` for `.working.md` files older than **10 minutes** and resets them to `.ready.md`:

```
STORY-NNN.[complexity].working.md  →  STORY-NNN.[complexity].ready.md
```

The complexity segment is preserved so the story can be immediately re-claimed without going through the orchestrator again.

---

## Stories

### File format

```markdown
# STORY-NNN: [easy|medium|hard] <Short Title>

**Index**: N                        ← priority order; lower = worked first
**Complexity**: easy | medium | hard ← assigned by BA; used by orchestrator and agents
**Design ref**: workspace/design/<feature>.processed.md | workspace/design/<feature>.new.md
**Depends on**: STORY-NNN | none

## Context
## Acceptance Criteria
## Implementation Hints
## Test Requirements

---
<!-- Coding Agent appends timestamped failure notes below this line -->
```

### States

Complexity and state are encoded directly in the filename — no database or external state store.

| Filename pattern | State | Written by | Who acts next |
|---|---|---|---|
| `STORY-NNN.md` | **Unprocessed** | Business Analyst | Story Orchestrator |
| `STORY-NNN.[c].ready.md` | **Ready** | Story Orchestrator (or Coding Agent harness on reset) | Coding Agent (matching complexity) |
| `STORY-NNN.[c].working.md` | **In progress** | Coding Agent harness (Python) | — (owned by one agent) |
| `STORY-NNN.[c].done.md` | **Complete** | Coding Agent harness (Python) | Nobody |
| `STORY-NNN.[c].failed.md` | **Failed** | Coding Agent harness (Python) | Nobody |

Note: the **Coding Agent harness** means the Python `run()` loop, not the LLM session. The LLM writes an outcome sentinel (`done` or `failed`) to `<workspace>/.sentinels/STORY-NNN.outcome`; Python reads it and performs the story file rename. This ensures all story file state transitions happen on the main branch, never inside a story branch.

`[c]` = `easy`, `medium`, or `hard`.

### Lifecycle

```
BA writes STORY-NNN.md  (bare, unprocessed)
      │
      │  Story Orchestrator polls:
      │    - parses **Complexity** and **Depends on**
      │    - checks all deps have .done.md
      ▼
STORY-NNN.[complexity].ready.md    ← deps met; complexity confirmed
      │
      │  Coding Agent atomically claims (rename):
      ▼
STORY-NNN.[complexity].working.md  ← owned by exactly one Coding Agent
      │
      │  Agent implements story
      │
   ┌──┴────────────────────────┐
success                     failure
   │                            │
   │  write 'done' to           │  write 'failed' to outcome sentinel
   │  outcome sentinel          │  stop immediately
   │  stop immediately          │
   ▼                            ▼
   Python harness reads sentinel Python harness reads sentinel
   renames .working → .done.md  renames .working → .failed.md
```

### Parallel coordination

All coordination is via atomic filesystem operations — no database, no message queue, no shared memory.

| Operation | Mechanism |
|---|---|
| Mark story ready | Story Orchestrator renames `STORY-NNN.md` → `STORY-NNN.[c].ready.md` after dep check |
| Claim a story | Python agent renames `STORY-NNN.[c].ready.md` → `STORY-NNN.[c].working.md` — POSIX atomic; LLM session starts only after a claim succeeds |
| Story file state transition | Python reads `<workspace>/.sentinels/STORY-NNN.outcome` after each LLM session and renames the `.working.md` file accordingly — never done inside the LLM session |
| Complexity routing | Junior agents glob `*.easy.ready.md`; Senior agents glob `*.medium.ready.md` + `*.hard.ready.md` |
| Pipeline shutdown | `workspace/.sentinels/pipeline_complete` sentinel written by `start-team.sh` on Ctrl+C |
| Stale agent recovery | Watchdog resets `.[c].working.md` files idle > 10 minutes → `.[c].ready.md` |

---

## Development

```bash
# Lint
ruff check .
ruff format .

# Type check
mypy scripts/

# Tests
pytest
```
