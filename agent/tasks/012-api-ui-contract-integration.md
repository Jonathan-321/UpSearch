# Task 012: Persistent Trace And Live Run Contract

## Goal

Persist run trace events and expose restart-safe run state through the API and
review UI without changing the packet-generation behavior.

## Read

- `.upsearch/agent-runs/011-run-state-worker-integration-handoff.md`
- `docs/architecture/adr-002-run-state-and-events.md`
- `upsearch/orchestrator_service.py`
- `db.py`, only run records and trace-related schema/helpers
- `server.py`, only Opportunity OS stream and run-status endpoints
- `upsearch/packet_checkup.py`
- `frontend/src/hooks/useOS.ts`
- `frontend/src/components/HarnessCheckup.tsx`

## Write Scope

- `db.py`
- `upsearch/orchestrator_service.py`
- `upsearch/packet_checkup.py`
- `upsearch/api_schemas.py` (new)
- `server.py`
- `frontend/src/types.ts`
- `frontend/src/hooks/useOS.ts`
- `frontend/src/components/HarnessCheckup.tsx`
- `tests/test_trace_persistence.py` (new)
- `tests/test_api_contract.py` (new)
- `.upsearch/agent-runs/012-api-ui-contract-integration-handoff.md`

## Required Behavior

1. Persist every step, handoff, retry, gate, and error event by run ID.
2. Run state survives server restart and can be queried independently of an
   active SSE connection.
3. SSE emits keepalive events during long agent calls.
4. Historical packets without trace metadata remain `unavailable`, not failed.
5. API responses provide typed run, trace, QA, approval, and handoff readiness.
6. Review UI renders explicit backend states rather than inferring them from
   event counts.
7. Tests use temporary SQLite and fake agents; no network.

## Commands

```bash
uv run pytest -q tests/test_trace_persistence.py tests/test_api_contract.py
uv run pytest -q
cd frontend && npm run build
git diff --check
```

Write the handoff and stop after verification.
