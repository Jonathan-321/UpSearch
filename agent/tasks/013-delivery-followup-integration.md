# Task 013: Delivery And Follow-Up Integration

## Goal

Connect approved action records, send events, delivery state, and follow-ups so
the user can see what happened after a platform handoff without enabling
automatic sending.

## Read

- `.upsearch/agent-runs/012-api-ui-contract-integration-handoff.md`
- `upsearch/connectors.py`
- `db.py`, only messages, approvals, send events, and follow-ups
- `server.py`, only message, approval, delivery, and follow-up endpoints
- `frontend/src/components/ApprovalQueue.tsx`
- `frontend/src/hooks/useOS.ts`

## Write Scope

- `db.py`
- `server.py`
- `upsearch/api_schemas.py`
- `frontend/src/types.ts`
- `frontend/src/hooks/useOS.ts`
- `frontend/src/components/ApprovalQueue.tsx`
- `tests/test_delivery_followup.py` (new)
- `.upsearch/agent-runs/013-delivery-followup-integration-handoff.md`

Do not implement automatic sending or require real Gmail/LinkedIn APIs.

## Required Behavior

1. Send events record prepared, opened, sent, delivered, failed, and unknown
   states without falsely claiming delivery.
2. Delivery updates are idempotent and tied to the approved message digest.
3. Failed or unknown delivery preserves the approval record and exposes a safe
   retry decision.
4. Follow-up state is queryable and shown in the approval queue.
5. Stale or edited messages cannot inherit delivery or follow-up state.
6. Tests require no external platform or network.

## Commands

```bash
uv run pytest -q tests/test_delivery_followup.py
uv run pytest -q
cd frontend && npm run build
git diff --check
```

Write the handoff and stop after verification.
