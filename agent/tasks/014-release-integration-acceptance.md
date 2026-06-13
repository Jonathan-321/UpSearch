# Task 014: Release Integration Acceptance

## Goal

Prove the complete local deployment as one coherent, restart-safe,
approval-safe system before declaring the Phase 1 architecture stable.

## Read

- handoffs for Tasks 009 through 013
- `docs/deployment.md`
- `scripts/run-golden-acceptance.sh`
- `docker-compose.yml`
- health, run-state, message, delivery, and follow-up API routes

## Write Scope

- `scripts/run-release-acceptance.sh` (new)
- `tests/test_release_integration.py` (new)
- `docs/release-checklist.md` (new)
- `.upsearch/agent-runs/014-release-integration-acceptance-handoff.md`

Do not add new product features.

## Required Behavior

1. Start from an empty temporary state directory.
2. Initialize database and report healthy readiness.
3. Run Baseten and Modal golden acceptance.
4. Execute one packet through the shared application service with fake
   model/connectors.
5. Verify one run ID across packet, trace, metrics, and persisted state.
6. Verify action blocked before exact approval and actionable after approval.
7. Record a send event, delivery update, and follow-up without automatic send.
8. Restart and recover without duplicate packet, approval, trace, or send event.
9. Produce a concise release report and explicit remaining manual checks.

## Commands

```bash
bash scripts/run-release-acceptance.sh
uv run pytest -q tests/test_release_integration.py
uv run pytest -q
cd frontend && npm run build
docker compose config
git diff --check
```
