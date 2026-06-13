# Task 007: Approval And External-Action Safety

## Goal

Prove that external platform handoffs cannot occur from stale, mismatched,
duplicated, rejected, or unapproved message state.

## Read

- `upsearch/connectors.py`
- `db.py`, only approval, message, send-event, and follow-up functions
- `server.py`, only `/os/messages` and approval endpoints
- `frontend/src/components/ApprovalQueue.tsx`

## Write Scope

- `upsearch/connectors.py`
- `db.py`
- `server.py`
- `tests/test_action_safety.py` (new)
- `.upsearch/agent-runs/007-action-safety-handoff.md`

Do not implement automatic sending. Platform handoff must remain a reviewed
human action.

## Required Behavior

1. Approval records bind exact message ID, target, channel, body digest,
   attachment set, and schedule.
2. Editing any bound field invalidates previous approval.
3. Duplicate approval and duplicate send-event recording are idempotent.
4. Rejected, quarantined, stale, or failed-QA messages cannot become actionable.
5. Connector failure preserves approval and draft state without recording a
   successful send.
6. Tests require no Gmail, LinkedIn, browser, or network access.

## Commands

```bash
uv run pytest -q tests/test_action_safety.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
