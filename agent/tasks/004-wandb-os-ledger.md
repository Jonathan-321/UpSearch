# Task 004: Opportunity OS W&B Ledger

## Goal

Record Opportunity OS run quality and cost metadata in W&B without making W&B
a runtime dependency or storing credentials.

## Read First

- `upsearch/tracking.py`
- `upsearch/tracker.py`
- `upsearch/harnessed_orchestrator.py`
- `upsearch/schemas.py`
- `upsearch/config.py`

## Write Scope

- `upsearch/tracking.py`
- `upsearch/tracker.py`
- `upsearch/harnessed_orchestrator.py`
- `tests/test_os_tracking.py` (new)

## Required Behavior

1. Local JSONL logging always works.
2. W&B logging is optional and fails open.
3. Log route, latency, source count, verification state, QA score, retries, and
   final packet status.
4. Never log prompt bodies, credentials, private profile text, or outreach
   recipient contact data.
5. Tests use a fake tracker and require no network.

## Commands

```bash
uv run pytest -q tests/test_os_tracking.py
uv run pytest -q
git diff --check
```
