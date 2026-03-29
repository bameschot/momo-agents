# Momo Agents — System Design

## What It Is

A multi-agent coding team built on the Claude Agent SDK. The user describes what they want to build; a pipeline of specialised agents turns that description into a design, breaks it into stories, orchestrates which stories are ready to implement, implements the stories in parallel using tier-matched agents, and escalates to the user only when something is genuinely stuck.

---

## Repository Layout

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
├── design/                    ← Designer Agent outputs
│   ├── <feature>.new.md       ← written/updated by Designer; queued for BA
│   └── <feature>.processed.md ← renamed by BA after stories are generated
├── stories/                   ← story files; complexity + state encoded in filename
│   ├── STORY-001.md                      ← unprocessed (written by BA)
│   ├── STORY-002.easy.ready.md           ← deps met; ready for Junior Agent
│   ├── STORY-003.medium.working.md       ← claimed by a Senior Agent
│   ├── STORY-004.easy.done.md            ← complete
│   ├── STORY-005.hard.failed.md          ← exhausted retries; awaiting review
│   ├── STORY-006.medium.reviewing.md     ← claimed by Story Reviewer
│   └── HALT                              ← sentinel: all Coding Agents must pause
├── workspace/                 ← generated source code
│   ├── CLAUDE.md              ← build/test/lint instructions for Coding Agents
│   ├── src/
│   └── tests/
├── start-team.sh              ← launches all agents simultaneously
├── reset-team.sh              ← wipes all artefacts; resets to clean state
├── status.sh                  ← live story-state summary
└── watchdog.sh                ← resets stale .working.md files after 10 min
```

---

## Agents and Their Roles

| Agent | Role | Reads from | Writes to |
|---|---|---|---|
| **Designer** | Multi-turn interactive Q&A with user; writes design on `write` command | User input (terminal) | `design/` |
| **Business Analyst** | Watches `design/` for `*.new.md` files; decomposes each into stories with a `**Complexity**` field; renames to `*.processed.md` | `design/*.new.md` | `stories/STORY-NNN.md` |
| **Project Initialiser** | Scaffolds `workspace/` once when it is empty | `design/` | `workspace/` |
| **Story Orchestrator** | Watches `stories/` for bare `STORY-NNN.md` files; parses complexity and dependencies; renames to `STORY-NNN.[complexity].ready.md` when deps are met | `stories/STORY-NNN.md`, `stories/*.done.md` | `stories/` |
| **Junior Coding Agent** (×N) | Claims and implements `easy` stories; polls indefinitely for new work | `stories/*.easy.ready.md`, `workspace/CLAUDE.md` | `workspace/` |
| **Senior Coding Agent** (×N) | Claims and implements `medium` and `hard` stories; polls indefinitely | `stories/*.medium.ready.md`, `stories/*.hard.ready.md`, `workspace/CLAUDE.md` | `workspace/` |
| **Story Reviewer** | Triages permanently-failed stories with user guidance; resets them to unprocessed | `stories/*.failed.md` | `stories/` |
| **Watchdog** | Resets stale `.working.md` files whose agent has died or stalled | `stories/` | `stories/` |

Each LLM agent reads its system prompt from the corresponding file in `roles/` at startup. `story_orchestrator.py` is a plain Python utility — it makes no LLM calls.

---

## Designer Agent

The Designer runs as a genuine multi-turn conversation backed by `ClaudeSDKClient`. A single SDK session persists for the entire conversation, preserving full context across turns.

### Conversation flow

1. Agent opens a session and greets the user, asking what they want to build.
2. The user types responses directly in the terminal; each message is sent to the agent via `client.query()`.
3. The agent asks clarifying questions — technology stack, constraints, integrations, non-functional requirements — until it has a complete and unambiguous picture.
4. The agent does **not** write anything to disk until the user types **`write`**.
5. On `write`: the agent produces a thorough design document and saves it to `design/<feature-name>.new.md`. This immediately queues the design for the Business Analyst.
6. If `design/<feature-name>.processed.md` already exists (an earlier version was processed), the agent still writes to `<feature-name>.new.md` — this re-queues the design and the BA will regenerate its stories.
7. The session continues — the user can keep refining and issue `write` again at any time.
8. Type `exit`, `quit`, or press `Ctrl+C` to end the session.

---

## Business Analyst Agent

The BA agent uses design file **state encoded in the filename** — no mtime tracking, no external state store. The Designer writes `*.new.md`; the BA processes it and renames it to `*.processed.md`. If the designer updates and re-saves a design as `*.new.md`, the BA picks it up again automatically.

### Design file states

| Filename | State | Written by | Meaning |
|---|---|---|---|
| `design/<feature>.new.md` | **new** | Designer Agent | Queued for BA; not yet processed |
| `design/<feature>.processed.md` | **processed** | Business Analyst | Stories have been generated for this version |

### Watch loop

1. Every 5 seconds, glob all `*.new.md` files in `design/`.
2. For each `<feature>.new.md` found: run `business_analyst_agent.py --design <file>`.
3. On completion, rename `<feature>.new.md` → `<feature>.processed.md`.
4. Sleep and repeat until `pipeline_complete` is written.

Each story written by the BA includes a `**Complexity**: easy | medium | hard` field and a `**Depends on**` field. Stories are written as bare `STORY-NNN.md` files; it is the Story Orchestrator's job to validate them and assign the `.ready` state.

---

## Project Initialiser Agent

Runs once automatically when the workspace is empty:

1. Reads the design document for technology stack and project structure.
2. Creates `workspace/CLAUDE.md` with build, test, and lint commands.
3. Scaffolds the initial directory layout, config files, and empty entry points.
4. Does **not** implement any story logic.

If `workspace/` already contains files beyond the skeleton `CLAUDE.md`, the initialiser skips immediately.

---

## Story Orchestrator

The Story Orchestrator is a **plain Python utility** (no LLM calls) that continuously watches `stories/` and manages the transition from unprocessed to ready.

### Responsibilities

- Scan for bare `STORY-NNN.md` files (written by the BA, not yet evaluated).
- Parse `**Complexity**` and `**Depends on**` fields from each file.
- Check whether all listed dependencies have a corresponding `STORY-NNN.[complexity].done.md` file.
- If all deps are done (or there are no deps): rename `STORY-NNN.md` → `STORY-NNN.[complexity].ready.md`.
- If deps are unmet: log the blocked story and re-check on the next poll.

### Why a separate orchestrator?

Moving dependency resolution out of the coding agents has two advantages:

1. **Coding agents stay simple** — they look only for `.ready.md` files with the right complexity; no dependency graph traversal inside a long-running LLM session.
2. **Automatic unblocking** — when a story finishes and becomes `.done.md`, the orchestrator detects it on the next poll and immediately marks any dependent stories as ready, without any agent needing to be aware.

### Poll interval

Default: 5 seconds. Configurable via `--poll-interval`.

---

## Coding Agents

The pipeline uses two tiers of coding agent, differentiated by the story complexity they handle:

| Agent | Handles | Default model |
|---|---|---|
| **Junior Coding Agent** | `easy` stories | `claude-haiku-4-5-20251001` |
| **Senior Coding Agent** | `medium` and `hard` stories | `claude-sonnet-4-6` |

Both agents follow the same loop structure.

### Polling behaviour

Coding Agents **never stop on their own** — they poll indefinitely for eligible work:

1. Wait for `workspace/CLAUDE.md` to exist (proof that the Project Initialiser has finished).
2. Wait for at least one `.ready.md` story of the correct complexity tier to appear.
3. Enter the main work loop:
   - If `pipeline_complete` exists → exit cleanly.
   - If `HALT` exists → wait for it to be removed, then resume.
   - Attempt to claim the lowest-numbered eligible `.ready.md` story.
   - On unexpected exit → retry after 10 seconds.

The agents continue polling even when all current stories are done, because the BA may write new stories at any time and the orchestrator will mark them ready automatically.

### Story claiming

Claiming is an atomic filesystem rename:

```
STORY-NNN.[complexity].ready.md  →  STORY-NNN.[complexity].working.md
```

POSIX `rename(2)` is atomic; if two agents race, exactly one succeeds and the other moves to the next candidate. The complexity segment is preserved in the filename throughout all state transitions.

### On success

```
STORY-NNN.[complexity].working.md  →  STORY-NNN.[complexity].done.md
```

Workspace changes are committed. The agent loops back and looks for another story.

### On failure

```
STORY-NNN.[complexity].working.md  →  STORY-NNN.[complexity].failed.md
                                         + stories/HALT created
```

Any implementation failure immediately halts the pipeline. All coding agents detect `HALT`, revert uncommitted workspace changes, rename their `.working.md` back to `.ready.md`, and wait for the Story Reviewer to resolve the failed story.

### HALT handling

On detecting `stories/HALT`:
1. Discard all uncommitted workspace changes (`git checkout -- workspace/`).
2. Rename `.[complexity].working.md` back to `.[complexity].ready.md`.
3. Wait until HALT is removed, then resume polling.

---

## Story Reviewer Agent

1. Watches for `stories/HALT` in a continuous loop.
2. On detection, atomically claims `STORY-NNN.[complexity].failed.md` → `STORY-NNN.[complexity].reviewing.md`.
3. Reads the full story file including all accumulated failure notes.
4. Presents the user with the original goal, acceptance criteria, and a plain-language summary of each failed attempt.
5. Asks the user how to proceed (new approach, relaxed constraints, split the story, etc.).
6. Rewrites the entire file with a clean, updated story; preserves `**Index**` and `**Depends on**`.
7. Renames `STORY-NNN.[complexity].reviewing.md` → `STORY-NNN.md` (bare, no complexity or state).
   - This returns the story to the **unprocessed** queue. The Story Orchestrator will re-evaluate the rewritten content and re-assign complexity and readiness.
8. Once all `.failed.md` stories are resolved: deletes `stories/HALT`.
9. Returns to watching for the next HALT.

---

## Story File Format

```markdown
# STORY-NNN: [easy|medium|hard] <Short Title>

**Index**: N                        ← priority order; lower = worked first
**Complexity**: easy | medium | hard ← assigned by BA; used by orchestrator and agents
**Design ref**: design/<feature>.md
**Depends on**: STORY-NNN | none

## Context
## Acceptance Criteria
## Implementation Hints
## Test Requirements

---
<!-- Coding Agent appends timestamped failure notes below this line -->
```

---

## Story Lifecycle

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
success                     failure
   │                            │
   ▼                            ▼
STORY-NNN.[complexity].done.md   create stories/HALT
(commit workspace)               rename to .failed.md
                                              │
                                   All Coding Agents detect HALT:
                                   revert workspace, release to .ready.md, wait
                                              │
                                   Story Reviewer claims:
                                   .failed.md → .reviewing.md
                                   rewrites story with user guidance
                                   renames → bare STORY-NNN.md
                                   deletes HALT when all .failed.md resolved
                                              │
                                   Story Orchestrator re-evaluates bare .md
                                   → marks .ready.md again
                                              │
                                   Coding Agents resume automatically
```

---

## Story States

| Filename pattern | State | Written by | Who claims it next |
|---|---|---|---|
| `STORY-NNN.md` | **Unprocessed** | Business Analyst | Story Orchestrator |
| `STORY-NNN.[c].ready.md` | **Ready** | Story Orchestrator | Coding Agent (matching complexity) |
| `STORY-NNN.[c].working.md` | **In progress** | Coding Agent | — (owned by one agent) |
| `STORY-NNN.[c].done.md` | **Complete** | Coding Agent | Nobody |
| `STORY-NNN.[c].failed.md` | **Exhausted retries** | Coding Agent | Story Reviewer |
| `STORY-NNN.[c].reviewing.md` | **Under review** | Story Reviewer | — (owned by reviewer) |
| `HALT` *(sentinel)* | **System paused** | Coding Agent | Triggers stop + revert in all Coding Agents |

`[c]` = `easy`, `medium`, or `hard`.

---

## Parallel Coordination

All agent coordination is via atomic filesystem operations — no database, no message queue, no shared memory.

| Operation | Mechanism |
|---|---|
| Mark story ready | Story Orchestrator renames `STORY-NNN.md` → `STORY-NNN.[c].ready.md` after dep check |
| Claim a story | Coding Agent renames `STORY-NNN.[c].ready.md` → `STORY-NNN.[c].working.md` — POSIX atomic |
| Complexity routing | Filename pattern: Junior agents glob `*.easy.ready.md`; Senior agents glob `*.medium.ready.md` + `*.hard.ready.md` |
| Halt detection | Check for `stories/HALT` before claiming; wait in loop until removed |
| Workspace revert | `git checkout -- workspace/` on HALT detection |
| Pipeline shutdown | `pipeline_complete` sentinel written by `start-team.sh` on Ctrl+C |
| Stale agent recovery | Watchdog resets `.[c].working.md` files idle > 10 minutes → `.[c].ready.md` |

---

## `start-team.sh` — Usage Guide

`start-team.sh` launches all agents **simultaneously**, each in its own named terminal window. Agents self-coordinate via the filesystem; no window waits for another to finish before starting.

### Syntax

```bash
./start-team.sh <feature-name> [options]
```

| Flag | Description | Default |
|---|---|---|
| `feature-name` | Kebab-case name of the feature being built | required |
| `--junior-agents N` | Junior Coding Agents to spawn (easy stories) | `2` |
| `--senior-agents N` | Senior Coding Agents to spawn (medium/hard stories) | `1` |
| `--model-designer M` | Model for Designer Agent | `claude-sonnet-4-6` |
| `--model-ba M` | Model for Business Analyst | `claude-sonnet-4-6` |
| `--model-pi M` | Model for Project Initialiser | `claude-sonnet-4-6` |
| `--model-junior M` | Model for Junior Coding Agents | `claude-haiku-4-5-20251001` |
| `--model-senior M` | Model for Senior Coding Agents | `claude-sonnet-4-6` |
| `--model-reviewer M` | Model for Story Reviewer | `claude-sonnet-4-6` |

### Agent windows opened

| Window title | Agent | Notes |
|---|---|---|
| `🎨 Designer Agent` | Interactive design session | Type requirements; `write` saves the design |
| `📋 Business Analyst` | Design watcher | Polls `design/` every 5 s for `*.new.md` |
| `🏗️ Project Initialiser` | Workspace scaffolder | Runs once; skips if workspace already populated |
| `🎯 Story Orchestrator` | Readiness manager | Continuously marks stories ready as deps complete |
| `🐕 Watchdog` | Stale story reset | Runs continuously; resets stories idle > 10 min |
| `🔍 Story Reviewer` | Failed-story triage | Wakes on HALT; interactive with user |
| `🟢 Junior Coding Agent N [easy]` | Easy story implementation | Polls for `*.easy.ready.md` |
| `🔵 Senior Coding Agent N [medium/hard]` | Medium/hard story implementation | Polls for `*.medium.ready.md` + `*.hard.ready.md` |

### Shutting down

Press **`Ctrl+C`** in the `start-team.sh` terminal. This:
1. Writes `.sentinels/pipeline_complete` — signals all agent windows to exit cleanly.
2. Kills the watchdog process.
3. Prints a final per-agent token-usage summary and `status.sh` snapshot.
4. Removes the `.sentinels/` directory.

---

## `reset-team.sh` — Usage Guide

`reset-team.sh` wipes all generated artefacts and returns the repository to a clean state.

```bash
./reset-team.sh        # interactive — asks for confirmation
./reset-team.sh --yes  # non-interactive
```

| Path | What gets deleted |
|---|---|
| `stories/` | All `STORY-*` files in every state and the `HALT` sentinel |
| `design/` | All `*.md` design documents |
| `.sentinels/` | Entire directory |
| `workspace/` | All generated source code, tests, `CLAUDE.md`, and build artefacts |

---

## Watchdog (`watchdog.sh`)

Runs continuously alongside Coding Agents. Every 60 seconds it scans `stories/` for `.working.md` files older than **10 minutes** and resets them to `.ready.md`:

```
STORY-NNN.[complexity].working.md  →  STORY-NNN.[complexity].ready.md
```

The complexity segment is preserved so the story can be immediately re-claimed by an appropriate agent without going through the orchestrator again.

---

## Observability (`status.sh`)

Prints a live count and list of stories in each state:

```
$ ./status.sh

  unprocessed    2   STORY-001.md  STORY-007.md
  ready          1   STORY-002.easy.ready.md
  working        1   STORY-003.medium.working.md
  done           4   STORY-004.easy.done.md  ...
  failed         0
  reviewing      0
  HALT           no
```

Run at any time from any terminal to check pipeline progress.
