# Task 011: Scheduler Orchestrator Integration

## Goal

Move scheduler packet execution onto the unified orchestrator service while
preserving rediscovery, duration, retry, progress-report, and restart behavior.

## Read

- `.upsearch/agent-runs/010-application-boundary-integration-handoff.md`
- `docs/architecture/target-state.md`
- `upsearch/orchestrator_service.py`
- `run_scheduler.py`
- `upsearch/runtime.py`
- scheduler tests

## Write Scope

- `upsearch/orchestrator_service.py`
- `run_scheduler.py`
- `upsearch/runtime.py`
- `tests/test_scheduler_orchestrator_integration.py` (new)
- `.upsearch/agent-runs/011-run-state-worker-integration-handoff.md`

Do not edit agents, server routes, frontend, or database schema.

## Required Behavior

1. Scheduler calls the same `run_pipeline` service as HTTP and CLI.
2. Agent modules are not imported or executed directly by the scheduler.
3. Scheduled retries keep the original run lineage and do not create duplicate
   packets.
4. Rediscovery interval, `--duration`, `--once`, and progress reports retain
   current behavior.
5. Interrupted jobs can resume through the existing recovery contract.
6. Tests use fake service execution and temporary persistence; no network.

## Commands

```bash
uv run pytest -q tests/test_scheduler_orchestrator_integration.py
uv run pytest -q
git diff --check
```

Write the handoff and stop after verification.
