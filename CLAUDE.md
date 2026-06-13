# UpSearch Agent Instructions

Read `agent/README.md`, then read only the assigned task file and the files
listed in that task's `write_scope` and `read_first` sections.

## Product Boundary

UpSearch turns a rough technical profile into a source-backed company packet:

```text
profile -> company -> problem -> people -> technical note -> outreach -> QA -> approval
```

It optimizes for credible technical conversations, not message volume.
External actions always require exact human approval.

## Execution Rules

1. Work on one task file at a time.
2. Stay inside its write scope. Do not opportunistically refactor.
3. Never invent a company, person, URL, source, or user experience claim.
4. Treat network failure and missing evidence as explicit states, not reasons
   to fabricate a fallback.
5. Prefer deterministic validation before another model call.
6. Do not edit `.env`, credentials, local databases, or generated output.
7. Do not commit, push, send messages, or trigger external actions.
8. Stop if the task requires a product-policy or architecture decision not
   already encoded in `agent/system.yaml`.
9. Run every acceptance command in the task file.
10. Write the final handoff to `.upsearch/agent-runs/<task-id>-handoff.md`
    using `agent/handoff-template.md`.

## Token Discipline

- Do not read the full repository.
- Do not read `docs/opportunity-intelligence/oppprep-seed/`.
- Use `rg` to locate a symbol before opening a large file.
- Do not restate the product history.
- Keep progress updates to one sentence.
- Keep the final response under 25 lines and point to the handoff file.

## Definition Of Done

A task is done only when its behavior is implemented, focused tests pass, the
broader test suite has no new failures, and the handoff states remaining risk.
