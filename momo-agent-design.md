# Momo Agents — System Design

## What It Is

A multi-agent coding team built on the Claude Agent SDK. The user describes what they want to build; a pipeline of specialised agents turns that description into a design, breaks it into stories, implements the stories in parallel, and escalates to the user only when something is genuinely stuck.

---

## Repository Layout

```
momo-agents/
├── python-agents/             ← Python agent implementations
│   ├── designer.py
│   ├── business_analyst.py
│   ├── project_initialiser.py
│   ├── coding_agent.py
│   └── story_reviewer.py
├── roles/                     ← system prompt files (one per agent)
│   ├── designer.md
│   ├── business-analyst.md
│   ├── project-initialiser.md
│   ├── coding-agent.md
│   └── story-reviewer.md
├── design/                    ← Designer Agent outputs
│   ├── <feature>.new.md       ← written/updated by Designer; queued for BA
│   └── <feature>.processed.md ← renamed by BA after stories are generated
├── stories/                   ← story files; state encoded in filename suffix
│   ├── STORY-001.md           ← pending
│   ├── STORY-002.working.md   ← claimed by a Coding Agent
│   ├── STORY-003.done.md      ← complete
│   ├── STORY-004.failed.md    ← exhausted retries; awaiting review
│   ├── STORY-005.reviewing.md ← claimed by Story Reviewer
│   └── HALT                   ← sentinel: all Coding Agents must pause
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
| **Business Analyst** | Watches `design/` for `*.new.md` files; decomposes each into stories; renames to `*.processed.md` | `design/*.new.md` | `stories/`, `design/` |
| **Project Initialiser** | Scaffolds `workspace/` once before any Coding Agent runs | `design/` | `workspace/` |
| **Coding Agent** (×N) | Claims and implements one story at a time; polls indefinitely for new work | `stories/`, `workspace/CLAUDE.md` | `workspace/` |
| **Story Reviewer** | Triages permanently-failed stories with user guidance | `stories/*.failed.md` | `stories/` |
| **Watchdog** | Resets stale `.working.md` files whose agent has died or stalled | `stories/` | `stories/` |

Each agent reads its system prompt from the corresponding file in `roles/` at startup.

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

### Implementation notes

- Uses `ClaudeSDKClient` (not the one-shot `query()`) so that the SDK session — and therefore Claude's conversation memory — spans the whole session.
- Allowed tools: `Read`, `Write` (for reading existing files and saving the design doc).
- Permission mode: `acceptEdits`.

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
2. For each `<feature>.new.md` found: run `business_analyst.py --design <file>`.
3. On completion, rename `<feature>.new.md` → `<feature>.processed.md` (overwrites any previous processed version for that feature).
4. Sleep and repeat until `pipeline_complete` is written.

If the designer revises a design and issues `write` again, it saves as `<feature>.new.md`. The BA finds it on the next poll and processes it, naturally overwriting the old `<feature>.processed.md`. No mtime tracking, no intermediate state files.

---

## Project Initialiser Agent

Runs once automatically when the workspace is empty:

1. Reads the design document for technology stack and project structure.
2. Creates `workspace/CLAUDE.md` with build, test, and lint commands.
3. Scaffolds the initial directory layout, config files, and empty entry points.
4. Does **not** implement any story logic.
5. Writes `.sentinels/pi.done` when complete — Coding Agents wait for this sentinel before starting.

If `workspace/` already contains files (beyond the skeleton `CLAUDE.md`), the initialiser skips immediately and writes the sentinel.

---

## Coding Agent

### Polling behaviour

Coding Agents **never stop on their own** — they poll indefinitely for eligible work. The agent loop:

1. Wait for `pi.done` sentinel (Project Initialiser has finished).
2. Enter the main work loop:
   - If `pipeline_complete` exists → exit cleanly.
   - If `HALT` exists → wait for it to be removed (Story Reviewer is working), then resume.
   - Attempt to claim and implement the next eligible story.
   - If no eligible story is currently available (all are working, done, or blocked by unresolved dependencies) → sleep briefly and poll again.
   - On unexpected exit code → retry after 10 seconds.

The agent continues polling even when all current stories are done, because the BA may write new stories at any time (e.g. after the designer updates the design document). The only way to stop a Coding Agent is via the `pipeline_complete` sentinel, which is written when the operator presses `Ctrl+C` in the `start-team.sh` terminal.

### Story claiming

Claiming is an atomic filesystem rename: `STORY-NNN.md` → `STORY-NNN.working.md`. POSIX `rename(2)` is atomic; if two agents race, exactly one succeeds and the other moves to the next candidate.

Before claiming, the agent reads `**Depends on**` from each candidate and skips any whose dependency is not yet `.done.md`.

### Workspace commit policy

Coding Agents do **not** commit workspace changes until a story is successfully completed and renamed `.done.md`. All in-progress work stays uncommitted, making a git-based revert clean and safe on HALT.

### HALT handling

On detecting `stories/HALT`:
1. Discard all uncommitted workspace changes (`git checkout -- workspace/`).
2. Rename `.working.md` back to `.md`.
3. Wait until HALT is removed, then resume polling.

---

## Story Reviewer Agent

1. Watches for `stories/HALT` in a continuous loop.
2. On detection, atomically claims `STORY-NNN.failed.md` → `STORY-NNN.reviewing.md`.
3. Reads the full story file including all accumulated failure notes.
4. Presents the user with the original goal, acceptance criteria, and a plain-language summary of each failed attempt.
5. Asks the user how to proceed (new approach, relaxed constraints, split the story, etc.).
6. Rewrites the entire file with a clean, updated story; resets `**Attempts**: 0`; preserves `**Index**` and `**Depends on**`.
7. If no more `.failed.md` files exist: deletes `stories/HALT`.
8. Renames `.reviewing.md` → `.md` — story re-enters the pending queue.
9. Returns to watching for the next HALT.

Exits cleanly when `pipeline_complete` is written.

---

## Story File Format

```markdown
# STORY-NNN: <Short Title>

**Index**: N          ← priority order; lower = worked first
**Attempts**: 0       ← incremented by each Coding Agent attempt; max 5
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
BA Agent writes STORY-NNN.md  (Attempts: 0)
      │
      │  Coding Agent polls → checks dependency → atomically claims:
      ▼
STORY-NNN.working.md   ← owned by exactly one Coding Agent
      │                  Attempts incremented on claim
   ┌──┴──────────────┐
success            failure
   │                   │  append failure note
   ▼                Attempts < 5?
STORY-NNN.done.md   ├─ yes → rename back to STORY-NNN.md  (pending again)
(commit workspace)  └─ no  → create stories/HALT
                             rename to STORY-NNN.failed.md
                                  │
                           all Coding Agents detect HALT:
                           revert workspace, release story, wait
                                  │
                     Story Reviewer claims .failed.md → .reviewing.md
                     summarises to user; rewrites story; resets Attempts
                     deletes HALT when all .failed.md resolved
                     renames .reviewing.md → .md
                                  │
                     Coding Agents resume polling automatically
```

---

## Story States

| Filename suffix | State | Who can claim it |
|---|---|---|
| `.md` | Pending | Any Coding Agent (dependency permitting) |
| `.working.md` | In progress | — (owned by one Coding Agent) |
| `.done.md` | Complete | Nobody |
| `.failed.md` | Exhausted retries | Story Reviewer Agent |
| `.reviewing.md` | Under review | — (owned by Story Reviewer) |
| `HALT` (sentinel) | System paused | Triggers stop + revert in all Coding Agents |

---

## Retry Policy

| Attempts so far | On next failure |
|---|---|
| 1 – 4 | Append failure note; release story back to pending |
| 5 | Append failure note; create `HALT`; mark `.failed.md` |

Each failure note records the attempt number, a UTC timestamp, and a summary of what went wrong.

---

## Parallel Coordination

All agent coordination is via atomic filesystem operations — no database, no message queue, no shared memory.

| Operation | Mechanism |
|---|---|
| Claim a story | `rename(STORY-NNN.md, STORY-NNN.working.md)` — POSIX atomic |
| Dependency check | Read `**Depends on**`; skip if dependency not `.done.md` |
| Halt detection | Check for `stories/HALT` before claiming; wait in loop until removed |
| Workspace revert | `git checkout -- workspace/` on HALT detection |
| Pipeline shutdown | `pipeline_complete` sentinel written by `start-team.sh` on Ctrl+C |
| Stale agent recovery | Watchdog resets `.working.md` files idle > 10 minutes |

---

## `start-team.sh` — Usage Guide

`start-team.sh` launches all agents **simultaneously**, each in its own named terminal window. Agents self-coordinate via the filesystem; no window waits for another to finish before starting.

### Syntax

```bash
./start-team.sh <feature-name> [--dev-agents N]
```

| Argument | Description | Default |
|---|---|---|
| `feature-name` | Kebab-case name of the feature being built. Used to derive the expected design file path (`design/<feature-name>.md`). | required |
| `--dev-agents N` | Number of parallel Coding Agents to spawn. All other agents always run as a single instance. | `2` |

### Examples

```bash
# Start with default 2 coding agents
./start-team.sh my-feature

# Start with 4 coding agents for a large story backlog
./start-team.sh my-feature --dev-agents 4

# Start with a single coding agent (useful for debugging)
./start-team.sh my-feature --dev-agents 1
```

### What happens on launch

1. The script detects the available terminal emulator (macOS Terminal.app, gnome-terminal, konsole, xfce4-terminal, mate-terminal, xterm, or tmux as fallback).
2. All agent windows open **simultaneously** — no sequential waiting.
3. Each window is named after its agent (via ANSI title escape codes and, on macOS, AppleScript `custom title`).
4. If `workspace/` is empty the Project Initialiser scaffolds it from the design; if it already has content the initialiser skips automatically.
5. The `start-team.sh` terminal itself becomes the **pipeline monitor** — it prints a status line whenever story counts change.

### Agent windows opened

| Window title | Agent | Notes |
|---|---|---|
| `Designer Agent` | Interactive design session | Type your requirements; type `write` to save the design |
| `Business Analyst` | Design watcher | Polls `design/` every 5 s; re-runs when any `.md` changes |
| `Project Initialiser` | Workspace scaffolder | Runs once; skips if workspace already populated |
| `Watchdog` | Stale story reset | Runs continuously until pipeline_complete |
| `Story Reviewer` | Failed-story triage | Wakes on HALT; interactive with user |
| `Coding Agent 1` … `Coding Agent N` | Implementation | Polls indefinitely for eligible stories |

### Shutting down

Press **`Ctrl+C`** in the `start-team.sh` terminal. This:
1. Writes `.sentinels/pipeline_complete` — signals all agent windows to exit cleanly.
2. Kills the watchdog process.
3. Removes the `.sentinels/` directory.
4. Prints a final `status.sh` summary.

The individual agent terminal windows remain open (showing their last output) until you close them manually.

### Terminal fallback (tmux)

If no graphical terminal is found, all agents open as panes in a tmux session named `momo-agents`. Attach with:

```bash
tmux attach -t momo-agents
```

---

## `reset-team.sh` — Usage Guide

`reset-team.sh` wipes all generated artefacts and returns the repository to a clean state, ready for a completely fresh run.

### Syntax

```bash
./reset-team.sh [--yes]
```

| Argument | Description |
|---|---|
| *(none)* | Interactive mode — prints a summary and asks for confirmation before deleting anything. |
| `--yes` | Non-interactive mode — skips the confirmation prompt. Useful in scripts. |

### What is removed

| Path | What gets deleted |
|---|---|
| `stories/` | All `STORY-*` files in every state (`.md`, `.working.md`, `.done.md`, `.failed.md`, `.reviewing.md`) and the `HALT` sentinel |
| `design/` | All `*.md` design documents |
| `.sentinels/` | Entire directory (config, wrapper scripts, mtime store, done flags) |
| `workspace/` | All generated source code, tests, and build artefacts |

### What is preserved

| Path | Why |
|---|---|
| `workspace/CLAUDE.md` | Build/test/lint instructions written by hand; not regenerated |
| `workspace/src/` | Skeleton directory with `.gitkeep` |
| `workspace/tests/` | Skeleton directory with `.gitkeep` |

### After reset

```bash
./start-team.sh <new-feature-name>
```

---

## Watchdog (`watchdog.sh`)

Runs continuously alongside Coding Agents. Every 60 seconds it scans `stories/` for `.working.md` files and checks each file's last-modified timestamp. Any story in `.working.md` state for more than **10 minutes** is assumed to belong to a dead or stalled agent and is reset to pending:

```
STORY-NNN.working.md  →  STORY-NNN.md
```

The watchdog does not revert workspace changes — those are handled by the agent itself on halt detection, or remain as uncommitted noise that the next successful agent cleans up via `git checkout -- workspace/`.

---

## Observability (`status.sh`)

Prints a live count and list of stories in each state:

```
$ ./status.sh

  pending    2   STORY-001.md  STORY-004.md
  working    1   STORY-002.working.md
  done       3   STORY-003  STORY-005  STORY-006
  failed     0
  reviewing  0
  HALT       no
```

Run at any time from any terminal to check pipeline progress.
