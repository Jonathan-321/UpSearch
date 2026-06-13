# ADR-001: System Boundaries

**Status**: Accepted  
**Date**: 2026-06-10  
**Context**: Current architecture has interleaved concerns in server.py. This ADR
defines each layer's responsibility and communication contract.

## Boundary Definitions

### 1. API Layer

**Location**: `server.py` (route handlers)

**Responsibility**:
- Route registration, HTTP parsing, response serialization
- SSE event formatting (`sse()` helper)
- CORS, middleware, error-to-HTTP-status mapping
- Health endpoints

**Must NOT**:
- Import agent modules directly (imports `orchestrator_service` instead)
- Contain business logic beyond serialization
- Write to the database directly (delegates to `orchestrator_service` or `db.py`)
- Know about model routing, agent harnesses, or checkup scoring internals

**Current violation**: SSE stream handler imports all 7 agents at module scope
and inlines DB writes (lines 33–39, 654–667, 692–694, etc. of server.py).

### 2. Application Service Layer (proposed)

**Location**: `upsearch/orchestrator_service.py`

**Responsibility**:
- Pipeline step dispatch in the correct order
- DB writes for each step (company, problems, people, packet, messages)
- Checkup gating by calling `packet_checkup.decide_action()`
- Retry state management (accepts and returns retry counts)
- Trace event collection
- Run record creation and status updates

**Contract**:
```python
def run_pipeline(
    company_name: str,
    lane: str,
    profile_text: str,
    *,
    progress_callback: Callable | None = None,
    retry_counts: dict | None = None,
) -> RunResult:
    ...
```

**Must NOT**:
- Parse HTTP requests or format SSE responses
- Import from `server.py`, `run_scheduler.py`, or frontend modules
- Depend on global state (settings and logger are passed in)

### 3. Domain Logic Layer

**Location**: `agents/*.py`, `upsearch/packet_checkup.py`, `upsearch/connectors.py`

**Responsibility**:
- Agent `run()` functions: take structured input, return dict output
- Packet checkup: evaluate packet quality, decide action (pass/retry/block)
- Approval gate: validate action intents, check body digests

**Contract**:
```python
# Agent convention
def run(*args, **kwargs) -> dict:
    return {"result": {...}, "source_urls": [...], ...}

# Checkup convention
def evaluate_packet(...) -> dict:  # returns score, metrics, trace
def decide_action(checkup, retry_counts) -> dict:  # returns action, reason
```

**Must NOT**:
- Import from `server.py`, `db.py`, or frontend modules
- Know about HTTP, SSE, or serialization
- Write to the database (return data for the service layer to write)

**Current violation**: `packet_checkup.py` imports `db` directly and calls
`db.get_company()`, `db.get_packet()`, etc. This tight coupling means checkup
cannot be unit tested without a live database. A future refactor should pass
data in rather than importing db.

### 4. Connector Layer

**Location**: `upsearch/sourcing/*`, `upsearch/model_router.py`, `upsearch/model_execution.py`

**Responsibility**:
- External API calls (web search, GitHub, RSS, HN)
- LLM model routing and execution
- URL fetching and HTML extraction

**Contract**:
- Return list of domain objects or empty list on failure
- Never raise network errors to the caller (catch and log)
- Never fabricate or hallucinate data

**Must NOT**:
- Import domain logic modules
- Write to the database
- Know about packet state, approval gates, or run IDs

### 5. Persistence Layer

**Location**: `db.py`

**Responsibility**:
- SQLite schema management and migrations
- CRUD operations for all entities
- Query helpers (evidence summary, pending approvals, etc.)

**Contract**:
```python
# All functions accept and return plain dicts or lists of dicts
def upsert_company(name: str, **kwargs) -> int: ...
def insert_problem(...) -> int: ...
def get_pending_approvals() -> list[dict]: ...
```

**Must NOT**:
- Import from `server.py`, agents, or domain logic
- Know about model routing, harnesses, or LLMs

### 6. Background Worker Layer

**Location**: `run_scheduler.py`

**Responsibility**:
- Job queue management (enqueue, dequeue, complete, fail, retry)
- Duration contracts (`--once`, `--duration N`)
- Rediscovery loop
- Progress report generation

**Contract**:
- Calls `orchestrator_service.run_pipeline()` for company packet jobs
- Never imports agent modules directly

**Must NOT**:
- Serve HTTP requests
- Format SSE events
- Write to tables other than `scheduled_jobs` (pipeline results go through service)

### 7. Observability Layer

**Location**: `upsearch/tracking.py`, `upsearch/tracker.py`

**Responsibility**:
- Structured metric collection and sanitization
- W&B log dispatch (fails open)
- Local JSONL logging (always writes)

**Contract**:
```python
logger.log_metrics(StructuredRunMetrics(...))
```

**Must NOT**:
- Block the pipeline on W&B failure
- Store PII or full message bodies
- Know about packet structure, approval state, or agent internals

### 8. UI Layer

**Location**: `frontend/src/`

**Responsibility**:
- Display pipeline progress (SSE stream)
- Show packet details, checkup results, approval queue
- Allow profile editing and company selection

**Contract**:
- All state comes from REST endpoints and SSE events
- No business logic beyond what the server exposes

**Must NOT**:
- Import from server modules
- Make decisions about external actions
- Store credentials or API keys

## Boundary Violation Log

| Violation | Location | Severity | Fix |
|-----------|----------|----------|-----|
| API layer imports agents directly | `server.py` lines 33–39 | High | Delegate through `orchestrator_service` |
| API layer inlines DB writes | `server.py` SSE handler | High | Move to `orchestrator_service` |
| Domain logic imports persistence | `packet_checkup.py` imports db | Medium | Pass data as argument instead |
| Pipeline logic duplicated in 3 places | `server.py` SSE, `harnessed_orchestrator.py`, batch endpoint | High | Unify in `orchestrator_service` |
| App module imports from `db.py` directly | `packet_checkup.py` | Low | Refactor in a later pass |
