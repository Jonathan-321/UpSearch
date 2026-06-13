# Task 020: Outreach Draft Robustness

## Goal

Run 4 of the live Baseten packet crashed at packet persistence with
`'NoneType' object has no attribute 'strip'`: the outreach model emitted a
`null` variant in its JSON and the orchestrator called `.strip()` on it.
Drafts must always be non-empty strings.

## Read

- `agents/outreach.py`
- `upsearch/orchestrator_service.py`, only the draft persistence loop

## Write Scope

- `agents/outreach.py`
- `upsearch/orchestrator_service.py` (one guard)
- `tests/test_outreach_drafts.py` (new)
- `.upsearch/agent-runs/020-outreach-draft-robustness-handoff.md`

## Required Behavior

1. The outreach agent drops null, non-string, and whitespace-only variants
   at the source; the unparseable-output fallback stays.
2. The orchestrator's message-persistence loop tolerates non-string values.

## Commands

```bash
uv run pytest -q tests/test_outreach_drafts.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
