# Target Architecture

Last updated: 2026-06-10

## Principle

Preserve every working agent, database table, UI component, and test. The
migration sequence removes duplication before adding new capability. No working
path is rewritten — only unified.

## 1. Target Component Map

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend (unchanged)                                        │
│  PacketStudio | HarnessCheckup | ApprovalQueue               │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP + SSE
┌───────────────────────▼─────────────────────────────────────┐
│  server.py (slimmed API layer)                               │
│                                                               │
│  Route groups (unchanged surface, refactored internals):     │
│                                                               │
│  /api/*    — legacy quick-search (scout→analyst→strategist→  │
│              writer→log); unchanged as dead-code boundary    │
│  /os/*     — packet endpoints delegate to a single           │
│              orchestrator entry point                        │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  orchestrator_service.py  (NEW)                              │
│                                                               │
│  Single entry point: run_pipeline(company, lane, profile)     │
│                                                               │
│  Owns:                                                       │
│  - Pipeline step dispatch (7 agents)                         │
│  - DB writes (inserts, upserts, clear)                       │
│  - Checkup gating (delegates to packet_checkup)              │
│  - Retry logic (state-driven, not ad-hoc)                    │
│  - Trace event collection                                    │
│  - Run record creation                                       │
│                                                               │
│  Called identically by:                                      │
│  - SSE stream handler (server.py)                            │
│  - Batch pipeline (server.py)                                │
│  - Scheduler (run_scheduler.py)                              │
│  - CLI / tests                                               │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  agents/  (unchanged — each agent keeps its run() fn)       │
│  upsearch/ (unchanged — harness, tracking, routing, etc.)   │
└──────┬──────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  db.py (extended — run_records table, NO migration changes   │
│  to existing tables)                                         │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│  run_scheduler.py (refactored — calls orchestrator_service,  │
│  no longer imports agents directly)                          │
└─────────────────────────────────────────────────────────────┘
```

## 2. Smallest Migration Sequence

### Step 1: Extract `orchestrator_service.py` (Task 010)

- Move the centralized pipeline logic into `upsearch/orchestrator_service.py`
- Implement a `RunRecord` table in `db.py` to persist run_id, start/end time, steps completed, trace events path, final status
- SSE handler delegates to `orchestrator_service.run_pipeline()` and emits events based on progress callbacks
- `harnessed_orchestrator.py` is deprecated (tests preserved for safety, moved to integration bucket)
- **No agent changes. No DB migration to existing tables. No frontend changes.**

### Step 2: Unify the scheduler (Task 011)

- `run_scheduler.py` imports `orchestrator_service` instead of individual agents
- Enqueue/dispatch uses `RunRecord` for traceability
- Scheduler writes status to `RunRecord` instead of `.upsearch/loop-summary/`
- `--once` and `--duration` contract preserved
- **No endpoint changes.**

### Step 3: Event persistence and recovery (Task 012)

- `trace_events` are written to a `trace_events` table keyed by run_id
- SSE handler can resume a partially-complete pipeline by reading run state
- Proxy keepalive pings (every 15s) added to SSE stream
- **No agent changes. No frontend changes.**

### Step 4: Delivery tracking (Task 013)

- `send_events` table gains `delivery_confirmed_at` and `delivery_status` columns
- Optional webhook receiver for delivery confirmations
- Follow-up table surfaced in UI
- **Minimal DB migration (nullable columns). Small frontend addition.**

## 3. What Stays Unchanged

| Module | Status | Reason |
|--------|--------|--------|
| All `agents/*.py` | Unchanged | Core domain logic, well-tested |
| `db.py` schema (existing tables) | Unchanged | All current data contracts |
| `upsearch/tracking.py` | Unchanged | W&B + JSONL logging contract |
| `upsearch/model_router.py` | Unchanged | Route resolution works |
| `upsearch/model_execution.py` | Unchanged | LLM call wrapper |
| `upsearch/packet_checkup.py` | Unchanged | Gating and checkup logic |
| `upsearch/profile_harness.py` | Unchanged | Proof extraction |
| `upsearch/profile_source_fetch.py` | Unchanged | Source enrichment |
| `upsearch/connectors.py` | Unchanged | ApprovalGate and digest |
| `upsearch/runtime.py` | Unchanged | Startup/health/migrations |
| `frontend/` | Unchanged | UI contract preserved |
| All existing tests | Preserved | Regression safety net |

## 4. Mermaid Diagram — Target Pipeline Flow

```mermaid
flowchart LR
    A[User Profile] --> B[orchestrator_service.run_pipeline]
    B --> C[profile_agent]
    B --> D[company_agent]
    B --> E[problem_agent]
    B --> F[people_agent]
    B --> G[technical_note_agent]
    B --> H[outreach_agent]
    B --> I[qa_agent]
    B --> J[RunRecord]
    B -.->|progress_callback| K[SSE Stream | Scheduler]
    K --> L[Frontend | Loop summary]
    B --> M[db.py - packets, problems, people, messages]
    M --> N[Approval Queue]
    N --> O[connectors.py - platform handoff]
    O --> P[send_events + follow_ups]
```

## 5. Integration Boundary Diagram

```mermaid
flowchart TD
    subgraph "API Layer (server.py)"
        REST[/os/ endpoints]
        SSE[/os/packet/stream]
        BATCH[/os/batch]
    end
    subgraph "Application Service"
        OS[orchestrator_service.py]
    end
    subgraph "Domain Logic"
        AGENTS[agents/*.py]
        CHECKUP[packet_checkup.py]
        HARNESS[AgentHarness]
    end
    subgraph "Connectors"
        WEB[web_search, rss_feeds]
        GITHUB[github_org_search]
        COMPANY[company_people]
        ROUTER[ModelRouter]
    end
    subgraph "Persistence"
        DB[(SQLite via db.py)]
        JSONL[(JSONL logs)]
    end
    subgraph "Background Workers"
        SCHED[run_scheduler.py]
    end
    subgraph "Observability"
        WB[W&B]
        LOGGER[RunLogger]
    end
    subgraph "UI"
        REACT[React App]
    end

    REST --> OS
    SSE --> OS
    BATCH --> OS
    SCHED --> OS
    OS --> AGENTS
    OS --> CHECKUP
    OS --> DB
    AGENTS --> WEB
    AGENTS --> GITHUB
    AGENTS --> COMPANY
    AGENTS --> ROUTER
    OS --> LOGGER
    LOGGER --> WB
    LOGGER --> JSONL
    DB --> REACT
    REACT --> REST
    REACT --> SSE
```

## 6. Migration Table

| Task | What | Risk | Depends On |
|------|------|------|-----------|
| 010 | Extract orchestrator_service.py, add RunRecord table, deprecate harnessed_orchestrator.py | Medium (integration surface) | None |
| 011 | Unify scheduler to use orchestrator_service | Low (scheduler imports change only) | 010 |
| 012 | Persist trace events, add SSE keepalive | Low (new table, no schema change to existing) | 010 |
| 013 | Delivery tracking, follow-up UI surface | Low (nullable columns) | None |

Each task's acceptance: existing test suite still passes, no behavioral change visible in UI, no regression in approval or action safety.
