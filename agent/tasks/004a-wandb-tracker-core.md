# Task 004a: Optional W&B Tracker Core

## Goal

Make the existing tracker persist safe structured run metrics locally and
optionally mirror them to W&B without requiring network access or credentials.

## Read

- `upsearch/tracking.py`
- `upsearch/tracker.py`
- `upsearch/config.py`

## Write Scope

- `upsearch/tracking.py`
- `upsearch/tracker.py`
- `tests/test_os_tracking.py` (new)
- `.upsearch/agent-runs/004a-wandb-tracker-core-handoff.md`

Do not edit the orchestrator or frontend.

## Required Behavior

1. Local JSONL logging always works.
2. W&B logging is optional and fails open.
3. Only structured metadata is accepted: route, model, latency, source count,
   verification state, QA score, retries, and final packet status.
4. Reject or remove prompt bodies, credentials, private profile text, outreach
   content, email addresses, and recipient contact data.
5. Tests use a fake W&B client and require no network.

## Commands

```bash
uv run pytest -q tests/test_os_tracking.py
```

Stop after the focused tests pass. Write the handoff and do not begin
orchestrator integration.
