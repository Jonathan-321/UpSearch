# Task 010: Unified Orchestrator Service

## Goal

Extract one application-level pipeline service so the SSE route, batch route,
CLI, and future scheduler integration use the same agent order, retry policy,
database writes, trace events, metrics, and run ID.

## Read

- `.upsearch/agent-runs/009-architecture-synthesis-handoff.md`
- `docs/architecture/target-state.md`
- `docs/architecture/adr-001-system-boundaries.md`
- `docs/architecture/adr-002-run-state-and-events.md`
- `server.py`, only Opportunity OS pipeline routes
- `upsearch/harnessed_orchestrator.py`
- `orchestrator.py`
- `db.py`, only schema initialization and generated packet writes

## Write Scope

- `upsearch/orchestrator_service.py` (new)
- `upsearch/harnessed_orchestrator.py`
- `orchestrator.py`
- `server.py`
- `db.py`
- `tests/test_orchestrator_service.py` (new)
- `.upsearch/agent-runs/010-application-boundary-integration-handoff.md`

Do not edit agents, connectors, checkup rules, model routing, tracking, or the
frontend.

## Required Behavior

1. One `run_pipeline` contract owns the seven-stage pipeline.
2. One run ID follows agent execution, trace, metrics, persistence, and result.
3. SSE and batch HTTP routes delegate to the service instead of implementing
   agent execution or packet persistence themselves.
4. Existing `harnessed_orchestrator` and CLI public calls remain compatible
   through thin adapters.
5. The service preserves current agent order, retries, approval defaults, and
   packet database state.
6. Add an idempotent `run_records` table and public DB helpers defined by
   ADR-002.
7. Tests use fake agents and temporary SQLite; no network or credentials.

## Commands

```bash
uv run pytest -q tests/test_orchestrator_service.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
