# momo-agents

A multi-agent coding pipeline that takes a feature idea from concept through to working, tested code — without human intervention between steps. Supports two AI backends: the **Claude Agent SDK** (cloud) and a locally running **Ollama** instance (local/offline).

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
     Junior Coding Agent 2 ──┼►  Senior Coding Agent 2 ──┼──► <workspace>/
           [easy]            │         [medium/hard]      │
                             └─────────────┬──────────────┘
                                     (on failure)
                                           ▼
                                    Story Reviewer ──► You
```

The pipeline has one hard sequencing constraint: the **Project Initialiser** runs first and writes `CLAUDE.md` at the workspace root. The **Business Analyst** and all **Coding Agents** poll for this file and will not start work until it exists. Everything else is coordinated via atomic filesystem operations — no agent explicitly waits for another.

| Agent | Role | Reads from | Writes to |
|---|---|---|---|
| **Designer** | Multi-turn interactive Q&A with user; writes design on `write` command | User input (terminal) | `<workspace>/design/` |
| **Project Initialiser** | Reads the design, determines the correct tech-stack scaffolding, and writes `CLAUDE.md` at the workspace root; all other agents gate on this file | `<workspace>/design/` | `<workspace>/` |
| **Business Analyst** | Waits for `CLAUDE.md`, then watches `<workspace>/design/` for `*.new.md` files and decomposes each into story files with a **Complexity** field | `<workspace>/design/*.new.md`, `<workspace>/CLAUDE.md` | `<workspace>/stories/STORY-NNN.md` |
| **Story Orchestrator** | Plain Python utility (no LLM); watches `<workspace>/stories/` for bare `STORY-NNN.md` files, parses complexity and deps, renames to `STORY-NNN.[complexity].ready.md` when deps are met | `<workspace>/stories/STORY-NNN.md`, `<workspace>/stories/*.done.md` | `<workspace>/stories/` |
| **Junior Coding Agent** (×N) | Python outer loop claims one `easy` story at a time; starts a fresh LLM session per story; polls indefinitely for new work | `<workspace>/stories/*.easy.ready.md`, `<workspace>/CLAUDE.md` | `<workspace>/` |
| **Senior Coding Agent** (×N) | Python outer loop claims one `medium`/`hard` story at a time; starts a fresh LLM session per story; polls indefinitely | `<workspace>/stories/*.medium/hard.ready.md`, `<workspace>/CLAUDE.md` | `<workspace>/` |
| **Story Reviewer** | Wakes on `HALT`; triages failed stories with you, rewrites and resets them so the orchestrator can re-evaluate | `<workspace>/stories/*.failed.md` | `<workspace>/stories/` |
| **Watchdog** | Resets stale `.working.md` files whose agent has died or stalled (idle > 10 min) back to `.ready.md` | `<workspace>/stories/` | `<workspace>/stories/` |

Each LLM agent reads its system prompt from the corresponding file in `roles/` at startup. `story_orchestrator.py` makes no LLM calls.

---

## AI backends

### Claude (default)

Uses the [Claude Agent SDK](https://github.com/anthropics/claude-agent-sdk). Requires an Anthropic API key. Each agent script lives in `scripts/claude_agents/`.

### Ollama (local)

Uses a locally running [Ollama](https://ollama.com) instance. No API key required — models run entirely on your machine. Each agent script lives in `scripts/ollama_agents/` and shares common tool infrastructure from `scripts/ollama_agents/ollama_utilities.py`.

The Ollama agents implement their own agentic tool-call loop (`run_agent_loop` in `ollama_utilities.py`) using the OpenAI function-call format. The available tools per agent are:

| Agent | Tools |
|---|---|
| Designer | `read_file`, `write_file`, `glob` |
| Business Analyst | `read_file`, `write_file`, `glob` |
| Project Initialiser | `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep` |
| Junior / Senior Coding Agent | `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep` |
| Story Reviewer | `read_file`, `write_file`, `bash`, `glob`, `ask_user` |

Each Ollama agent has its own role file in `roles/ollama_roles/` (`ollama-*.md`) that documents every tool by name, its parameters, and concrete call examples — this is important because local models cannot infer tool behaviour from context the way large cloud models can.

**Robustness features** — `ollama_utilities.py` implements two mechanisms to cope with common local-model failure modes:

- **Text-embedded tool call detection**: some models output tool call JSON as plain text rather than using the structured function-call mechanism. Both `run_agent_loop` and `run_chat_loop` scan every text-only response for JSON objects matching a known tool name, execute any found, and feed the results back to the model — exactly as if a structured call had been made.
- **Continuation prompts**: models sometimes emit a text-only planning turn between steps (e.g. after reading a design document, before writing files). When no tool call — structured or text-embedded — is found, the agent loop re-prompts the model with a task-specific continuation message rather than exiting prematurely. Up to three consecutive text-only turns are tolerated before the loop accepts the response as a genuine completion. Both mechanisms apply to every agent that uses `run_agent_loop`; the designer's `run_chat_loop` applies text-embedded detection only (the interactive prompt handles the "no tool call" case).

**Recommended models** (reliable tool calling is the critical factor):

| Tier | Model | Best for |
|---|---|---|
| Best overall | `qwen2.5-coder:14b` | Senior agent, Project Initialiser |
| Good, faster | `qwen2.5-coder:7b` | Junior agent |
| Better prose | `qwen2.5:14b` | Business Analyst, Story Reviewer |
| Strong code | `codestral:22b` | Senior agent (less consistent tool calling) |
| Compact reasoning | `phi4:14b` | BA / Reviewer alternative |

For a suggested per-role model configuration see the [examples below](#examples).

---

## Ollama agent tools

Each Ollama agent is given a fixed set of tools at startup. All tool implementations live in `scripts/ollama_agents/ollama_utilities.py` and are dispatched by a shared `ToolExecutor`. The table below shows which agents receive which tools, followed by a description of every tool.

### Tool availability by agent

| Tool | Designer | Business Analyst | Project Initialiser | Junior Coding | Senior Coding | Story Reviewer |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `read_file` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `write_file` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `edit_file` | | | ✓ | ✓ | ✓ | |
| `bash` | | | ✓ | ✓ | ✓ | ✓ |
| `glob` | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `grep` | | | ✓ | ✓ | ✓ | |
| `ask_user` | | | | | | ✓ |

The tools are grouped into four named collections in `ollama_utilities.py`:

| Collection | Tools | Used by |
|---|---|---|
| `DESIGNER_TOOLS` | `read_file`, `write_file`, `glob` | Designer |
| `ANALYST_TOOLS` | `read_file`, `write_file`, `glob` | Business Analyst |
| `CODING_TOOLS` | `read_file`, `write_file`, `edit_file`, `bash`, `glob`, `grep` | Project Initialiser, Junior Coding, Senior Coding |
| `REVIEWER_TOOLS` | `read_file`, `write_file`, `glob`, `bash`, `ask_user` | Story Reviewer |

---

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
| `command` | string | ✓ | Shell command to run |

Runs via `subprocess.run()` with a **120-second timeout**. Returns the combined stdout and stderr along with the exit code. Used by coding agents to run build tools, test runners, linters, formatters, git commands, and any other CLI operations needed to implement or verify a story. The Story Reviewer uses it to inspect git history or run diagnostic commands before consulting the user.

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

Runs `grep -rn -E` under the hood. Used by coding agents and the Project Initialiser to locate definitions, imports, usages, or configuration values across the workspace without reading every file individually.

---

#### `ask_user`
Present a question to the user and block until they reply.

| Parameter | Type | Required | Description |
|---|---|:---:|---|
| `question` | string | ✓ | The question or prompt to display |
| `choices` | array of strings | | Optional list of options; printed as a numbered menu alongside the question |

Writes the question to stdout and reads a line from stdin. When `choices` is provided the options are numbered and printed below the question, but the user may type any free-form response. Used exclusively by the Story Reviewer to gather human guidance on how to handle a failed story — for example, whether to change the approach, relax acceptance criteria, or split the story into smaller pieces.

---

## Repository layout

```
momo-agents/
├── scripts/
│   ├── agent_utilities.py         ← shared helpers (path utils, run-log writer, workspace wait)
│   ├── token_logger.py            ← shared JSONL token-usage logger and console printer
│   ├── story_orchestrator.py      ← non-LLM; shared by all agent types; marks stories ready
│   ├── claude_agents/             ← agents backed by the Claude Agent SDK
│   │   ├── claude_designer_agent.py
│   │   ├── claude_business_analyst_agent.py
│   │   ├── claude_project_initialiser_agent.py
│   │   ├── claude_junior_coding_agent.py      ← claims easy stories
│   │   ├── claude_senior_coding_agent.py      ← claims medium/hard stories
│   │   └── claude_story_reviewer_agent.py
│   └── ollama_agents/             ← agents backed by a local Ollama instance
│       ├── ollama_utilities.py            ← shared tool defs, ToolExecutor, agent loops, text-tool-call fallback
│       ├── ollama_designer_agent.py
│       ├── ollama_business_analyst_agent.py
│       ├── ollama_project_initialiser_agent.py
│       ├── ollama_junior_coding_agent.py
│       ├── ollama_senior_coding_agent.py
│       └── ollama_story_reviewer_agent.py
├── roles/                     ← system prompt files (one per LLM agent)
│   ├── claude_roles/                  ← prompts for the Claude backend
│   │   ├── claude_designer.md
│   │   ├── claude_business-analyst.md
│   │   ├── claude_project-initialiser.md
│   │   ├── claude_junior-coding-agent.md
│   │   ├── claude_senior-coding-agent.md
│   │   └── claude_story-reviewer.md
│   └── ollama_roles/                  ← prompts for the Ollama backend
│       ├── designer.md                ← same prompt as Claude designer (shared)
│       ├── ollama-business-analyst.md
│       ├── ollama-project-initialiser.md
│       ├── ollama-junior-coding-agent.md
│       ├── ollama-senior-coding-agent.md
│       └── ollama-story-reviewer.md
├── workspace/                 ← all generated artefacts
│   ├── CLAUDE.md              ← build/test/lint instructions; start gate for agents
│   ├── design/                ← Designer Agent outputs
│   │   ├── <feature>.new.md       ← written by Designer; queued for BA
│   │   └── <feature>.processed.md ← renamed by BA after stories are generated
│   ├── stories/               ← story files; complexity + state encoded in filename
│   │   ├── STORY-001.md                      ← unprocessed (written by BA)
│   │   ├── STORY-002.easy.ready.md           ← deps met; ready for Junior Agent
│   │   ├── STORY-003.medium.working.md       ← claimed by a Senior Agent
│   │   ├── STORY-004.easy.done.md            ← complete
│   │   ├── STORY-005.hard.failed.md          ← failed; awaiting review
│   │   ├── STORY-006.medium.reviewing.md     ← claimed by Story Reviewer
│   │   └── HALT                              ← sentinel: all Coding Agents must stop
│   ├── .sentinels/            ← runtime coordination files (created by start-team.sh)
│   │   ├── pipeline_complete      ← written on Ctrl+C; signals all agents to exit
│   │   ├── config.sh              ← shared env vars sourced by wrapper scripts
│   │   ├── run-log.jsonl          ← pipeline event log (one JSON entry per line)
│   │   ├── tokens/                ← per-agent JSONL token usage logs
│   │   └── run_*.sh               ← agent wrapper scripts
│   ├── src/
│   └── tests/
├── start-team.sh              ← launches all agents simultaneously
├── reset-team.sh              ← wipes all artefacts; resets to clean state
├── run_report.py              ← generates the HTML run report (run log + token usage)
├── status.sh                  ← live story-state summary
└── watchdog.sh                ← resets stale .working.md files after 10 min
```

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
3. Writes each story as `<workspace>/stories/STORY-NNN.md` (bare, unprocessed — awaiting the Story Orchestrator).
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
| **Junior Coding Agent** | `easy` stories | `claude-haiku-4-5-20251001` | `qwen2.5-coder:7b` |
| **Senior Coding Agent** | `medium` and `hard` stories | `claude-sonnet-4-6` | `qwen2.5-coder:7b` |

Both agents follow the same structure: **Python owns the outer loop; a fresh LLM session is started for every story.** This keeps each session's context small and avoids the quadratic token cost that accumulates when tool-call history from previous stories remains in context.

For the **Ollama backend**, each coding agent passes a continuation prompt to the agent loop. If the model produces a text-only response mid-session the loop first checks whether the text contains a JSON-encoded tool call and executes it if found; if not, it re-prompts the model with an explicit continuation instruction rather than exiting prematurely.

**Python startup** (once, before the loop):
1. Poll every 10 s until `<workspace>/CLAUDE.md` exists.
2. Read `<workspace>/CLAUDE.md` and retain the content in memory for the lifetime of the process.

**Python outer loop**:
1. Check for `<workspace>/stories/HALT` or `<workspace>/.sentinels/pipeline_complete` — exit if either exists.
2. Atomically claim the lowest-numbered `.ready.md` story of the correct complexity tier by renaming it to `.working.md`. POSIX `rename(2)` is atomic — if two agents race, exactly one succeeds; the other moves to the next candidate.
3. If no story can be claimed, sleep 10 s and retry.
4. Start a **fresh LLM session** for the claimed story, passing the story path and the pre-read `<workspace>/CLAUDE.md` content directly in the task prompt.
5. After the session ends: check whether `.done.md` or `.failed.md` now exists and log accordingly, then loop back to step 1.

**Per-story LLM session**:
1. Read the story file.
2. Read the design document(s) listed in the story's **Design ref** field — both possible paths are listed separated by ` | `; read whichever exist.
3. Note the `## Agent Exclusion List` in `CLAUDE.md` — never read from or write to those paths.
4. Implement the acceptance criteria in `<workspace>/`.
5. Run tests and linter as instructed in `CLAUDE.md`.
6. Check for `<workspace>/stories/HALT` before committing — if found, perform the halt procedure immediately.
7. **On success**: rename `.[complexity].working.md` → `.[complexity].done.md`, commit workspace changes.
8. **On failure**: create `<workspace>/stories/HALT`, rename `.[complexity].working.md` → `.[complexity].failed.md`, perform halt procedure. No retries.

---

### Story Reviewer

A **one-shot agent** — `start-team.sh` invokes it when it detects that `<workspace>/stories/HALT` exists. The agent processes all currently-failed stories in a single LLM session and then exits. The continuous watch loop for the HALT file lives in `start-team.sh`.

**Python startup**:
1. Checks whether `<workspace>/stories/HALT` exists — if not, prints a message and exits immediately.
2. Globs all `STORY-*.failed.md` files.
3. If HALT exists but no failed stories are found: removes the stale HALT file and exits.
4. Starts a single LLM session covering all failed stories, then waits for completion.
5. After the session: warns if the HALT file still exists (some stories may not have been resolved).

**LLM session behaviour** (per failed story, in order):
1. Atomically claims the next `.failed.md` story by renaming it to `.[complexity].reviewing.md`.
2. Reads the full story file, including any appended failure notes.
3. Presents the user with the story goal, acceptance criteria, and a plain-language summary of each failed attempt.
4. Asks the user how to proceed — new approach, relaxed constraints, split the story, or skip it.
5. Rewrites the story file based on the user's guidance; preserves `**Index**` and `**Depends on**`; removes all failure notes.
6. Renames `.[complexity].reviewing.md` → bare `STORY-NNN.md` — returns it to the unprocessed queue so the Story Orchestrator re-evaluates it with the rewritten content.
7. Repeats steps 1–6 for each remaining failed story.
8. Deletes `<workspace>/stories/HALT` once all failed stories have been resolved.
9. Notifies the user that the pipeline is ready to resume.

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
| `STORY-NNN.[c].ready.md` | **Ready** | Story Orchestrator | Coding Agent (matching complexity) |
| `STORY-NNN.[c].working.md` | **In progress** | Coding Agent | — (owned by one agent) |
| `STORY-NNN.[c].done.md` | **Complete** | Coding Agent | Nobody |
| `STORY-NNN.[c].failed.md` | **Failed** | Coding Agent | Story Reviewer |
| `STORY-NNN.[c].reviewing.md` | **Under review** | Story Reviewer | — (owned by reviewer) |
| `HALT` *(sentinel)* | **System paused** | Coding Agent | Triggers stop + revert in all Coding Agents |

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
   ┌──┴────────────────────────┐
success                     failure (no retry)
   │                            │
   ▼                            ▼
STORY-NNN.[complexity].done.md   create workspace/stories/HALT
(commit workspace)               rename to .failed.md
                                 coding agent exits
                                              │
                                   Story Reviewer claims:
                                   .failed.md → .reviewing.md
                                   rewrites story with user guidance
                                   renames → bare STORY-NNN.md
                                   deletes HALT when all .failed.md resolved
                                              │
                                   Story Orchestrator re-evaluates bare .md
                                   → marks .ready.md again
```

### Parallel coordination

All coordination is via atomic filesystem operations — no database, no message queue, no shared memory.

| Operation | Mechanism |
|---|---|
| Mark story ready | Story Orchestrator renames `STORY-NNN.md` → `STORY-NNN.[c].ready.md` after dep check |
| Claim a story | Python agent renames `STORY-NNN.[c].ready.md` → `STORY-NNN.[c].working.md` — POSIX atomic; LLM session starts only after a claim succeeds |
| Complexity routing | Junior agents glob `*.easy.ready.md`; Senior agents glob `*.medium.ready.md` + `*.hard.ready.md` |
| Halt detection | Check for `workspace/stories/HALT` before and after implementation; exit immediately if found |
| Workspace revert | Discard uncommitted changes on HALT detection |
| Pipeline shutdown | `workspace/.sentinels/pipeline_complete` sentinel written by `start-team.sh` on Ctrl+C |
| Stale agent recovery | Watchdog resets `.[c].working.md` files idle > 10 minutes → `.[c].ready.md` |

---

## Setup

### Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- **Claude backend**: an Anthropic API key
- **Ollama backend**: a running [Ollama](https://ollama.com) instance with at least one model pulled (e.g. `ollama pull qwen2.5-coder:7b`)

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
ollama pull qwen2.5-coder:7b
```

---

## Running the pipeline

### Start the full team

```bash
./start-team.sh --workspace <path> [options]
```

Opens every agent simultaneously in its own named terminal window and monitors the pipeline in the current terminal until you press **Ctrl+C**. Each agent window prints its **mode** and **model** at startup so you can confirm configuration at a glance.

`<path>` is the workspace directory where all generated artefacts live. It can be anywhere on the filesystem — inside or outside the `momo-agents` repo. If the directory does not exist, `start-team.sh` will offer to create it and initialise a git repository inside it.

| Flag | Description | Default |
|---|---|---|
| `--workspace <path>` | Path to the workspace directory (required) | — |
| `--agent-type TYPE` | AI backend: `claude` or `ollama` | `claude` |
| `--ollama-host URL` | Ollama API base URL (Ollama mode only) | `http://localhost:11434` |
| `--junior-agents N` | Number of parallel Junior Coding Agents (easy stories) | `2` |
| `--senior-agents N` | Number of parallel Senior Coding Agents (medium/hard stories) | `1` |
| `--model-designer M` | Model for the Designer | see defaults below |
| `--model-ba M` | Model for the Business Analyst | see defaults below |
| `--model-pi M` | Model for the Project Initialiser | see defaults below |
| `--model-junior M` | Model for Junior Coding Agents | see defaults below |
| `--model-senior M` | Model for Senior Coding Agents | see defaults below |
| `--model-reviewer M` | Model for the Story Reviewer | see defaults below |

**Model defaults:**

| Agent | `--agent-type claude` | `--agent-type ollama` |
|---|---|---|
| Designer | `claude-sonnet-4-6` | `qwen2.5-coder:7b` |
| Business Analyst | `claude-sonnet-4-6` | `qwen2.5-coder:7b` |
| Project Initialiser | `claude-haiku-4-5-20251001` | `qwen2.5-coder:7b` |
| Junior Coding Agent | `claude-haiku-4-5-20251001` | `qwen2.5-coder:7b` |
| Senior Coding Agent | `claude-sonnet-4-6` | `qwen2.5-coder:7b` |
| Story Reviewer | `claude-sonnet-4-6` | `qwen2.5-coder:7b` |

**Agent windows opened:**

| Window | Agent | Notes |
|---|---|---|
| `🎨 Designer Agent` | Interactive design session | Type requirements; `write` saves the design |
| `🏗️ Project Initialiser` | Workspace scaffolder | Runs once; skips if workspace already populated |
| `📋 Business Analyst` | Design watcher | Polls `<workspace>/design/` every 5 s; waits for `<workspace>/CLAUDE.md` |
| `🎯 Story Orchestrator` | Readiness manager | Continuously marks stories ready as deps complete |
| `🐕 Watchdog` | Stale story reset | Resets stories idle > 10 min back to `.ready.md` |
| `🔍 Story Reviewer` | Failed-story triage | Wakes on HALT; interactive with you |
| `🟢 Junior Coding Agent N` | Easy story implementation | Waits for `<workspace>/CLAUDE.md`; polls for `*.easy.ready.md` |
| `🔵 Senior Coding Agent N` | Medium/hard story implementation | Waits for `<workspace>/CLAUDE.md`; polls for `*.medium/hard.ready.md` |

**Examples:** <a name="examples"></a>

```bash
# Claude backend — 2 junior agents, 1 senior agent (defaults)
./start-team.sh --workspace /path/to/my-project

# Ollama backend — all agents use local qwen2.5-coder (simplest config)
./start-team.sh --workspace /path/to/my-project --agent-type ollama

# Ollama — recommended per-role model split for best results
./start-team.sh --workspace /path/to/my-project \
  --agent-type ollama \
  --model-junior   qwen2.5-coder:7b  \
  --model-senior   qwen2.5-coder:7b \
  --model-pi       qwen2.5-coder:7b \
  --model-ba       qwen2.5:7b       \
  --model-reviewer qwen2.5:7b

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
```

### Monitor progress

```bash
./status.sh
```

Prints a live snapshot of how many stories are in each state:

```
  unprocessed    2   STORY-001.md  STORY-004.md
  ready          1   STORY-002.easy.ready.md
  working        1   STORY-003.medium.working.md
  done           3   STORY-005.easy.done.md  ...
  failed         0
  reviewing      0
  HALT           no
```

### Shut down

Press **Ctrl+C** in the `start-team.sh` terminal. This:

1. Writes `<workspace>/.sentinels/pipeline_complete` — all agent windows exit cleanly.
2. Kills the watchdog process and closes all opened agent terminal windows.
3. Prints a final per-agent token-usage summary and `status.sh` snapshot.
4. Generates a self-contained HTML run report and writes it to `<workspace>/run-report_YYYY-MM-DD_HH-MM-SS.html`.
5. Removes the `<workspace>/.sentinels/` directory.

The run report (generated by `run_report.py`) contains two sections:
- **Run Log** — every pipeline event recorded by agents (design written, project initiated, story created, story done/failed), ordered chronologically.
- **Token Usage** — per-agent breakdown of input, output, and cache tokens plus cost, with an interactive Chart.js timeline.

Open it in any browser after the run.

### Reset

**Reset stories only** (keep generated code):

```bash
rm -f <workspace>/stories/STORY-*.md <workspace>/stories/HALT
```

**Full reset** — wipe everything generated:

```bash
./reset-team.sh        # interactive — asks for confirmation
./reset-team.sh --yes  # non-interactive
```

| Path | What gets deleted |
|---|---|
| `<workspace>/stories/` | All `STORY-*` files in every state and the `HALT` sentinel |
| `<workspace>/design/` | All `*.md` design documents |
| `<workspace>/.sentinels/` | Entire directory (wrapper scripts, tokens, sentinels) |
| `<workspace>/` | All generated source code, tests, `CLAUDE.md`, and build artefacts |

After a full reset, re-running `./start-team.sh --workspace <path>` goes through the complete pipeline from scratch.

---

## Running agents individually

### Claude backend

```bash
# Designer (interactive)
python scripts/claude_agents/claude_designer_agent.py --model claude-sonnet-4-6

# Project Initialiser
python scripts/claude_agents/claude_project_initialiser_agent.py \
  --design workspace/design/my-feature.new.md \
  --model claude-sonnet-4-6

# Business Analyst (waits for workspace/CLAUDE.md before starting)
python scripts/claude_agents/claude_business_analyst_agent.py \
  --design workspace/design/my-feature.new.md \
  --workspace-dir workspace \
  --model claude-sonnet-4-6

# Story Orchestrator (no LLM — agent-type agnostic)
python scripts/story_orchestrator.py

# Junior Coding Agent (easy stories; waits for workspace/CLAUDE.md)
python scripts/claude_agents/claude_junior_coding_agent.py \
  --model claude-haiku-4-5-20251001

# Senior Coding Agent (medium/hard stories; waits for workspace/CLAUDE.md)
python scripts/claude_agents/claude_senior_coding_agent.py \
  --model claude-sonnet-4-6

# Story Reviewer
python scripts/claude_agents/claude_story_reviewer_agent.py \
  --model claude-sonnet-4-6
```

### Ollama backend

```bash
# Designer (interactive)
python scripts/ollama_agents/ollama_designer_agent.py --model qwen2.5-coder:7b

# Project Initialiser
python scripts/ollama_agents/ollama_project_initialiser_agent.py \
  --design workspace/design/my-feature.new.md \
  --model qwen2.5-coder:7b

# Business Analyst
python scripts/ollama_agents/ollama_business_analyst_agent.py \
  --design workspace/design/my-feature.new.md \
  --workspace-dir workspace \
  --model qwen2.5-coder:7b

# Junior Coding Agent (easy stories)
python scripts/ollama_agents/ollama_junior_coding_agent.py --model qwen2.5-coder:7b

# Senior Coding Agent (medium/hard stories)
python scripts/ollama_agents/ollama_senior_coding_agent.py --model qwen2.5-coder:7b

# Story Reviewer
python scripts/ollama_agents/ollama_story_reviewer_agent.py --model qwen2.5-coder:7b

# Override Ollama host for any agent:
python scripts/ollama_agents/ollama_junior_coding_agent.py \
  --model llama3.1 \
  --ollama-host http://192.168.1.10:11434
```

All path arguments default to `workspace/` relative to the `momo-agents` repo root when running agents individually. Pass `--workspace-dir <path>` to point them at any workspace directory.

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
