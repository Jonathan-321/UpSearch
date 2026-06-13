# Task 009: Architecture Synthesis And Integration Map

## Goal

Document the architecture that now exists after Tasks 001 through 008, identify
the remaining integration seams, and define a target architecture that can be
implemented incrementally without rewriting UpSearch.

## Read

- `docs/opportunity-intelligence/upsearch-first-use-case-charter.md`
- `.upsearch/agent-runs/001-people-source-connectors-handoff.md`
- `.upsearch/agent-runs/002-discovery-depth-handoff.md`
- `.upsearch/agent-runs/003-trace-integrity-handoff.md`
- `.upsearch/agent-runs/004a-wandb-tracker-core-handoff.md`
- `.upsearch/agent-runs/004b-wandb-orchestrator-handoff.md`
- `.upsearch/agent-runs/005-qa-routing-benchmark-handoff.md`
- `.upsearch/agent-runs/006-golden-packet-acceptance-handoff.md`
- `.upsearch/agent-runs/007-action-safety-handoff.md`
- `.upsearch/agent-runs/008-deployment-recovery-handoff.md`
- `server.py`, only imports, app lifecycle, and route groups
- `db.py`, only schema and public function groups
- `upsearch/harnessed_orchestrator.py`
- `run_scheduler.py`, only scheduler lifecycle and job dispatch
- `frontend/src/App.tsx`
- `frontend/src/hooks/useOS.ts`, only API calls and exposed state

## Write Scope

- `docs/architecture/current-state.md` (new)
- `docs/architecture/target-state.md` (new)
- `docs/architecture/integration-backlog.md` (new)
- `docs/architecture/adr-001-system-boundaries.md` (new)
- `docs/architecture/adr-002-run-state-and-events.md` (new)
- `.upsearch/agent-runs/009-architecture-synthesis-handoff.md`

Do not edit application code, tests, configuration, or the task queue.

## Required Deliverables

1. Current-state component map covering:
   profile ingestion, source connectors, company discovery, packet pipeline,
   QA/checkup, approvals, scheduler, SQLite, W&B/local ledger, frontend, and
   platform handoffs.
2. A data-flow diagram from user intake through follow-up state.
3. A run-state model describing ownership of run IDs, packet state, trace
   events, retries, approval records, send events, and follow-ups.
4. Explicit boundaries for:
   API layer, application services, domain logic, connectors, persistence,
   background workers, observability, and UI.
5. Honest inventory of duplicated logic, hidden coupling, stale contracts,
   and lifecycle risks.
6. Target architecture that preserves the working implementation and explains
   the smallest migration sequence.
7. Integration backlog ordered by risk and dependency, with acceptance
   criteria for Tasks 010 through 013.
8. Mermaid diagrams must render with valid syntax.

## Verification

```bash
python3 - <<'PY'
from pathlib import Path
required = [
    "docs/architecture/current-state.md",
    "docs/architecture/target-state.md",
    "docs/architecture/integration-backlog.md",
    "docs/architecture/adr-001-system-boundaries.md",
    "docs/architecture/adr-002-run-state-and-events.md",
]
for item in required:
    text = Path(item).read_text()
    assert len(text) >= 800, item
    assert "```mermaid" in text or "adr-" in item, item
print("architecture artifacts present")
PY
git diff --check
```

Write the handoff and stop after verification.
