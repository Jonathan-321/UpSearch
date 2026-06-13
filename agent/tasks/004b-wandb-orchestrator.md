# Task 004b: Opportunity OS Tracker Integration

## Goal

Wire the verified tracker core into the Opportunity OS orchestrator.

## Read

- `.upsearch/agent-runs/004a-wandb-tracker-core-handoff.md`
- `upsearch/harnessed_orchestrator.py`
- `upsearch/schemas.py`
- the public tracker API added by Task 004a

## Write Scope

- `upsearch/harnessed_orchestrator.py`
- `tests/test_os_tracking_integration.py` (new)
- `.upsearch/agent-runs/004b-wandb-orchestrator-handoff.md`

## Required Behavior

Log route, model, latency, source count, verification state, QA score, retries,
and final packet status. Do not log prompts, private profile text, outreach
content, credentials, email addresses, or recipient contact data.

## Commands

```bash
uv run pytest -q tests/test_os_tracking_integration.py
uv run pytest -q
git diff --check
```
