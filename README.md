# momo-agents

A multi-agent coding pipeline powered by the Claude Agent SDK. A team of specialised agents collaborate over the filesystem to take a feature idea from concept through to working, tested code — without human intervention between steps.

---

## Pipeline overview

```
  You ──► Designer ──► Project Initialiser
                              │
                    writes workspace/CLAUDE.md
                              │
               ┌──────────────┴──────────────────────┐
               ▼                                     ▼
     Business Analyst                       Story Orchestrator
    (waits for CLAUDE.md,                  (marks stories ready
     then decomposes design)                when deps are met)
               │                                     │
               └──────────────┬──────────────────────┘
                              ▼
             (waits for workspace/CLAUDE.md)
               ┌──────────────┴──────────────┐
               ▼                             ▼
     Junior Coding Agent 1 ──┐   Senior Coding Agent 1 ──┐
     Junior Coding Agent 2 ──┼►  Senior Coding Agent 2 ──┼──► workspace/
           [easy]            │         [medium/hard]      │
                             └─────────────┬──────────────┘
                                     (on failure)
                                           ▼
                                    Story Reviewer ──► You
```

The pipeline has one hard sequencing constraint: the **Project Initialiser** runs first and writes `workspace/CLAUDE.md`. The **Business Analyst** and all **Coding Agents** poll for this file and will not start work until it exists. Everything else is coordinated via atomic filesystem operations — no agent explicitly waits for another.

| Agent | Role | Reads from | Writes to |
|---|---|---|---|
| **Designer** | Multi-turn interactive Q&A with user; writes design on `write` command | User input (terminal) | `workspace/design/` |
| **Project Initialiser** | Reads the design, determines the correct tech-stack scaffolding, and writes `workspace/CLAUDE.md`; all other agents gate on this file | `workspace/design/` | `workspace/` |
| **Business Analyst** | Waits for `workspace/CLAUDE.md`, then watches `workspace/design/` for `*.new.md` files and decomposes each into story files with a **Complexity** field | `workspace/design/*.new.md`, `workspace/CLAUDE.md` | `workspace/stories/STORY-NNN.md` |
| **Story Orchestrator** | Plain Python utility (no LLM); watches `workspace/stories/` for bare `STORY-NNN.md` files, parses complexity and deps, renames to `STORY-NNN.[complexity].ready.md` when deps are met | `workspace/stories/STORY-NNN.md`, `workspace/stories/*.done.md` | `workspace/stories/` |
| **Junior Coding Agent** (×N) | Python outer loop claims one `easy` story at a time; starts a fresh LLM session per story; polls indefinitely for new work | `workspace/stories/*.easy.ready.md`, `workspace/CLAUDE.md` | `workspace/` |
| **Senior Coding Agent** (×N) | Python outer loop claims one `medium`/`hard` story at a time; starts a fresh LLM session per story; polls indefinitely | `workspace/stories/*.medium/hard.ready.md`, `workspace/CLAUDE.md` | `workspace/` |
| **Story Reviewer** | Wakes on `HALT`; triages failed stories with you, rewrites and resets them so the orchestrator can re-evaluate | `workspace/stories/*.failed.md` | `workspace/stories/` |
| **Watchdog** | Resets stale `.working.md` files whose agent has died or stalled (idle > 10 min) back to `.ready.md` | `workspace/stories/` | `workspace/stories/` |

Each LLM agent reads its system prompt from the corresponding file in `roles/` at startup. `story_orchestrator.py` makes no LLM calls.

---

## Repository layout

```
momo-agents/
├── scripts/                   ← Python agent and utility implementations
│   ├── designer_agent.py
│   ├── business_analyst_agent.py
│   ├── project_initialiser_agent.py
│   ├── story_orchestrator.py      ← non-LLM utility; marks stories ready
│   ├── junior_coding_agent.py     ← claims easy stories
│   ├── senior_coding_agent.py     ← claims medium/hard stories
│   ├── story_reviewer_agent.py
│   └── token_logger.py            ← shared JSONL token-usage logger
├── roles/                     ← system prompt files (one per LLM agent)
│   ├── designer.md
│   ├── business-analyst.md
│   ├── project-initialiser.md
│   ├── junior-coding-agent.md
│   ├── senior-coding-agent.md
│   └── story-reviewer.md
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
│   │   ├── tokens/                ← per-agent JSONL token usage logs
│   │   └── run_*.sh               ← agent wrapper scripts
│   ├── src/
│   └── tests/
├── start-team.sh              ← launches all agents simultaneously
├── reset-team.sh              ← wipes all artefacts; resets to clean state
├── status.sh                  ← live story-state summary
└── watchdog.sh                ← resets stale .working.md files after 10 min
```

---

## Agent details

### Designer

The Designer runs as a genuine multi-turn conversation backed by `ClaudeSDKClient`. A single SDK session persists for the entire conversation, preserving full context across turns.

1. Agent greets the user and asks what they want to build.
2. Asks clarifying questions — technology stack, constraints, integrations, non-functional requirements — until it has a complete picture.
3. Does **not** write anything to disk until the user types **`write`**.
4. On `write`: produces a thorough design document and saves it to `workspace/design/<feature-name>.new.md`, immediately queuing it for the Business Analyst.
5. If a `.processed.md` version already exists, writing a new `.new.md` re-queues the design and the BA regenerates stories.
6. The session continues — the user can keep refining and issue `write` again at any time.
7. Type `exit`, `quit`, or press **Ctrl+C** to end the session.

---

### Project Initialiser

Runs once automatically when the workspace is empty. Its primary output — `workspace/CLAUDE.md` — is the **start gate** for the Business Analyst and all Coding Agents.

1. Reads the design document and determines the correct tech-stack scaffolding (language, runtime, frameworks, tooling).
2. Creates `workspace/CLAUDE.md` with precise, runnable build, test, and lint commands for the identified stack.
3. Scaffolds the idiomatic directory layout, config files, and empty entry points for that stack.
4. Does **not** implement any story logic.

If `workspace/CLAUDE.md` already exists the initialiser skips immediately — the presence of that file is the sole signal that scaffolding has already been completed.

---

### Business Analyst

The BA agent uses design file **state encoded in the filename** — no mtime tracking, no external state store.

**Startup gate**: polls every 10 seconds until `workspace/CLAUDE.md` exists. This ensures stories are always written with full knowledge of the tech stack.

**Watch loop**:
1. Wait for `workspace/CLAUDE.md` to exist.
2. Every 5 seconds, glob all `*.new.md` files in `workspace/design/`.
3. For each `<feature>.new.md` found: decompose it into `workspace/stories/STORY-NNN.md` files.
4. On completion, rename `<feature>.new.md` → `<feature>.processed.md` inside `workspace/design/`.
5. Sleep and repeat until `pipeline_complete` is written.

Each story includes a `**Complexity**: easy | medium | hard` field and a `**Depends on**` field. Stories are written as bare `STORY-NNN.md` files; the Story Orchestrator assigns the `.ready` state.

The BA **strongly prefers easy and medium stories** and only uses hard when splitting would produce artificial or incoherent units of work. Complexity levels reflect realistic effort:

| Complexity | Effort | Meaning |
|---|---|---|
| **easy** | ~3 hours | Self-contained work with clear scope — a new module, a small integration, or several related changes within one subsystem |
| **medium** | ~6 hours | Multiple moving parts or significant design judgement — a feature spanning a few subsystems, a non-trivial algorithm, or a meaningful refactor |
| **hard** | > 6 hours | Broad cross-cutting changes, subtle concurrency/state management, or refactoring across many modules with unclear boundaries |

| Filename | State | Meaning |
|---|---|---|
| `workspace/design/<feature>.new.md` | **new** | Queued for BA; not yet processed |
| `workspace/design/<feature>.processed.md` | **processed** | Stories have been generated for this version |

---

### Story Orchestrator

A **plain Python utility** (no LLM calls) that continuously watches `workspace/stories/` and manages the unprocessed → ready transition.

- Scans for bare `STORY-NNN.md` files written by the BA.
- Parses `**Complexity**` and `**Depends on**` fields from each file.
- Checks whether all listed dependencies have a corresponding `.done.md` file.
- If all deps are done (or there are no deps): renames `STORY-NNN.md` → `STORY-NNN.[complexity].ready.md`.
- If deps are unmet: logs the blocked story and re-checks on the next poll.

Decoupling dependency resolution from the coding agents keeps the agents simple and enables automatic unblocking — when a story finishes, the orchestrator immediately marks any dependent stories as ready without any agent needing to be aware.

Default poll interval: 5 seconds (configurable via `--poll-interval`).

---

### Coding Agents

Two tiers handle stories by complexity:

| Agent | Handles | Default model |
|---|---|---|
| **Junior Coding Agent** | `easy` stories | `claude-haiku-4-5-20251001` |
| **Senior Coding Agent** | `medium` and `hard` stories | `claude-sonnet-4-6` |

Both agents follow the same structure: **Python owns the outer loop; a fresh LLM session is started for every story.** This keeps each session's context small and avoids the quadratic token cost that accumulates when tool-call history from previous stories remains in context.

**Python startup** (once, before the loop):
1. Poll every 60 s until `workspace/CLAUDE.md` exists.
2. Read `workspace/CLAUDE.md` and retain the content in memory for the lifetime of the process.

**Python outer loop**:
1. Check for `workspace/stories/HALT` or `pipeline_complete` sentinel — exit if either exists.
2. Atomically claim the lowest-numbered `.ready.md` story of the correct complexity tier by renaming it to `.working.md`. POSIX `rename(2)` is atomic — if two agents race, exactly one succeeds; the other moves to the next candidate.
3. If no story can be claimed, sleep 60 s and retry.
4. Start a **fresh `query()` session** for the claimed story, passing the story path and the pre-read `workspace/CLAUDE.md` content directly in the task prompt.
5. When the session ends, loop back to step 1.

**Per-story LLM session** (one `query()` call per story):
1. Read the story file fully.
2. Using the `workspace/CLAUDE.md` content provided in the task, identify generated/vendored/tooling folders to avoid reading.
3. Implement the acceptance criteria in `workspace/`.
4. Run tests and linter as instructed in `workspace/CLAUDE.md`.
5. Check for `workspace/stories/HALT` before committing. If found, perform the halt procedure.
6. **On success**: rename `.working.md` → `.done.md`, commit workspace changes.
7. **On failure**: create `workspace/stories/HALT`, rename `.working.md` → `.failed.md`, perform halt procedure. No retries.

---

### Story Reviewer

1. Watches for `workspace/stories/HALT` in a continuous loop.
2. Atomically claims `STORY-NNN.[complexity].failed.md` → `STORY-NNN.[complexity].reviewing.md`.
3. Reads the full story including any appended failure notes.
4. Presents the user with the original goal, acceptance criteria, and a summary of what failed.
5. Asks the user how to proceed (new approach, relaxed constraints, split the story, etc.).
6. Rewrites the file with a clean, updated story; preserves `**Index**` and `**Depends on**`.
7. Renames to bare `STORY-NNN.md` — returns it to the unprocessed queue so the orchestrator re-evaluates.
8. Deletes `workspace/stories/HALT` once all `.failed.md` stories are resolved.
9. Returns to watching for the next HALT.

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
**Design ref**: workspace/design/<feature>.md
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
- An Anthropic API key

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

# 4. Add your API key
echo "ANTHROPIC_API_KEY=your_key_here" > .env
```

---

## Running the pipeline

### Start the full team

```bash
./start-team.sh <feature-name> [options]
```

Opens every agent simultaneously in its own named terminal window and monitors the pipeline in the current terminal until you press **Ctrl+C**.

| Flag | Description | Default |
|---|---|---|
| `--junior-agents N` | Number of parallel Junior Coding Agents (easy stories) | `2` |
| `--senior-agents N` | Number of parallel Senior Coding Agents (medium/hard stories) | `1` |
| `--model-designer M` | Claude model for the Designer | `claude-sonnet-4-6` |
| `--model-ba M` | Claude model for the Business Analyst | `claude-sonnet-4-6` |
| `--model-pi M` | Claude model for the Project Initialiser | `claude-sonnet-4-6` |
| `--model-junior M` | Claude model for Junior Coding Agents | `claude-haiku-4-5-20251001` |
| `--model-senior M` | Claude model for Senior Coding Agents | `claude-sonnet-4-6` |
| `--model-reviewer M` | Claude model for the Story Reviewer | `claude-sonnet-4-6` |

**Agent windows opened:**

| Window | Agent | Notes |
|---|---|---|
| `🎨 Designer Agent` | Interactive design session | Type requirements; `write` saves the design |
| `🏗️ Project Initialiser` | Workspace scaffolder | Runs once; skips if workspace already populated |
| `📋 Business Analyst` | Design watcher | Polls `workspace/design/` every 5 s; waits for `workspace/CLAUDE.md` |
| `🎯 Story Orchestrator` | Readiness manager | Continuously marks stories ready as deps complete |
| `🐕 Watchdog` | Stale story reset | Resets stories idle > 10 min back to `.ready.md` |
| `🔍 Story Reviewer` | Failed-story triage | Wakes on HALT; interactive with you |
| `🟢 Junior Coding Agent N` | Easy story implementation | Waits for `workspace/CLAUDE.md`; polls for `*.easy.ready.md` |
| `🔵 Senior Coding Agent N` | Medium/hard story implementation | Waits for `workspace/CLAUDE.md`; polls for `*.medium/hard.ready.md` |

**Examples:**

```bash
# Default — 2 junior agents, 1 senior agent
./start-team.sh my-feature

# Scale up for a large backlog
./start-team.sh my-feature --junior-agents 4 --senior-agents 2

# Use opus for design, keep defaults elsewhere
./start-team.sh my-feature --model-designer claude-opus-4-6

# --flag=value form also works
./start-team.sh my-feature --junior-agents=3 --model-junior=claude-sonnet-4-6
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

1. Writes `workspace/.sentinels/pipeline_complete` — all agent windows exit cleanly.
2. Kills the watchdog process and closes all opened agent terminal windows.
3. Prints a final per-agent token-usage summary and `status.sh` snapshot.
4. Generates a self-contained HTML token usage report and writes it to `workspace/token-report_YYYY-MM-DD_HH-MM-SS.html`.
5. Removes the `workspace/.sentinels/` directory.

The token report includes a per-agent breakdown of input, output, and cache tokens plus cost, and an interactive Chart.js timeline. Open it in any browser after the run.

### Reset

**Reset stories only** (keep generated code):

```bash
rm -f workspace/stories/STORY-*.md workspace/stories/HALT
```

**Full reset** — wipe everything generated:

```bash
./reset-team.sh        # interactive — asks for confirmation
./reset-team.sh --yes  # non-interactive
```

| Path | What gets deleted |
|---|---|
| `workspace/stories/` | All `STORY-*` files in every state and the `HALT` sentinel |
| `workspace/design/` | All `*.md` design documents |
| `workspace/.sentinels/` | Entire directory (wrapper scripts, tokens, sentinels) |
| `workspace/` | All generated source code, tests, `CLAUDE.md`, and build artefacts |

After a full reset, re-running `./start-team.sh <feature-name>` goes through the complete pipeline from scratch.

---

## Running agents individually

Each agent can also be invoked directly:

```bash
# Designer (interactive)
python scripts/designer_agent.py --model claude-sonnet-4-6

# Project Initialiser
python scripts/project_initialiser_agent.py \
  --design workspace/design/my-feature.new.md \
  --model claude-sonnet-4-6

# Business Analyst (waits for workspace/CLAUDE.md before starting)
python scripts/business_analyst_agent.py \
  --design workspace/design/my-feature.new.md \
  --workspace-dir workspace \
  --model claude-sonnet-4-6

# Story Orchestrator
python scripts/story_orchestrator.py

# Junior Coding Agent (easy stories; waits for workspace/CLAUDE.md)
python scripts/junior_coding_agent.py \
  --model claude-haiku-4-5-20251001

# Senior Coding Agent (medium/hard stories; waits for workspace/CLAUDE.md)
python scripts/senior_coding_agent.py \
  --model claude-sonnet-4-6

# Story Reviewer
python scripts/story_reviewer_agent.py \
  --model claude-sonnet-4-6
```

All path arguments default to the standard locations inside the repo root.

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
