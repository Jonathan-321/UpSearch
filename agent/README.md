# UpSearch Agent Kit

This is the machine-readable operating layer for UpSearch. It exists so a
coding harness can execute bounded work without receiving the project history
in every prompt.

## Read Order

1. `/CLAUDE.md`
2. `/agent/system.yaml`
3. the assigned file in `/agent/tasks/`
4. only the code files named by that task
5. `/agent/verification.md`
6. `/agent/handoff-template.md`

## Model And Harness Roles

| Layer | Responsibility |
|---|---|
| DeepSeek in Claude Code | Bounded implementation, focused tests, mechanical fixes |
| Codex | Architecture, integration, cross-cutting changes, security review, final acceptance |
| Deterministic tools | Tests, builds, schemas, URL checks, word counts, static checks |
| Human | Product judgment, truth boundaries, credentials, and external actions |

DeepSeek is not a substitute for the orchestrator. It is a low-cost worker
inside a constrained coding harness.

## Queue

The ordered queue is in `agent/task-queue.yaml`. Execute one ready task only.
Do not start a second task in the same session.

## Launch

Interactive:

```bash
scripts/deepseek-session.sh
```

One bounded task:

```bash
scripts/deepseek-task.sh agent/tasks/001-people-source-connectors.md
```

Run the next task marked `ready`:

```bash
scripts/deepseek-next.sh
```

The task runner starts Claude Code through the local DeepSeek backdoor, applies
a turn limit, captures the JSON result in `.upsearch/agent-runs/`, and relies on
this kit instead of a large prompt.

Inspect the latest local Claude Code exchange without copying it into chat:

```bash
scripts/claude-session-tail.py --project . --messages 12
```

Session transcripts are a recovery tool, not the normal handoff mechanism.
