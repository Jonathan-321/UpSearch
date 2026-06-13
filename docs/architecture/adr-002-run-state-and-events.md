# ADR-002: Run State And Events

**Status**: Accepted  
**Date**: 2026-06-10  
**Context**: Current architecture has no persisted run record. Pipeline state is
in-memory and lost on restart. This ADR defines the run-state model and event
schema for the target architecture.

## 1. Run Record

A `run_records` table tracks every pipeline execution from start to completion.

```sql
CREATE TABLE IF NOT EXISTS run_records (
    id              INTEGER PRIMARY KEY,
    run_id          TEXT NOT NULL UNIQUE,        -- UUID v4
    company_name    TEXT NOT NULL,
    lane            TEXT NOT NULL DEFAULT 'ai_infra',
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'running',  -- running | complete | failed | cancelled
    steps_completed TEXT DEFAULT '[]',            -- JSON list of completed step names
    current_step    TEXT,                         -- name of the currently executing step
    qa_score        REAL,
    final_status    TEXT,                         -- prepared | needs_review
    trace_path      TEXT,                         -- path to persisted trace events (JSONL or table ref)
    error_message   TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Run lifecycle**:

```
created (on pipeline start)
  │
  ▼
running
  │
  ├── all steps complete ──► complete  (with qa_score and final_status)
  ├── unhandled exception ─► failed    (with error_message)
  └── user cancelled ──────► cancelled
```

**Step tracking**: As each pipeline step completes, `steps_completed` is updated
(e.g., `["profile", "company", "problem", "people"]`). The `current_step` field
allows recovery: on restart, the pipeline can resume from `current_step` instead
of starting over.

## 2. Trace Events Table

Persists the agent steps and handoffs that were previously held in-memory.

```sql
CREATE TABLE IF NOT EXISTS trace_events (
    id              INTEGER PRIMARY KEY,
    run_id          TEXT NOT NULL REFERENCES run_records(run_id),
    event_type      TEXT NOT NULL,                -- agent_step | handoff
    status          TEXT,                         -- ok | error | needs_review
    timestamp       TIMESTAMP NOT NULL,
    agent           TEXT,
    agent_role      TEXT,
    reads           TEXT DEFAULT '[]',            -- JSON list
    writes          TEXT DEFAULT '[]',            -- JSON list
    output_summary  TEXT,
    latency_ms      INTEGER,
    from_agent      TEXT,                         -- handoff only
    to_agent        TEXT,                         -- handoff only
    payload_keys    TEXT DEFAULT '[]',            -- handoff only
    reason          TEXT                          -- handoff only
);

CREATE INDEX idx_trace_run_id ON trace_events(run_id);
CREATE INDEX idx_trace_timestamp ON trace_events(timestamp);
```

**Access pattern**: Load all events for a run_id on startup, sorted by timestamp.
The checkup function receives this list as before but reads from the table
instead of an in-memory parameter.

## 3. Event Schema

### Agent Step Event

```python
{
    "event_type": "agent_step",
    "status": "ok",                    # ok | error | needs_review
    "timestamp": "2026-06-10T12:00:00Z",
    "agent": "company_sourcing",
    "agent_role": "Research fit, product area, hiring signal, and public sources.",
    "reads": ["company_name", "lane", "user_profile", "public_sources"],
    "writes": ["company_record", "company_sources"],
    "output_summary": "fit=8/10; sources=12",
    "latency_ms": 3400
}
```

### Handoff Event

```python
{
    "event_type": "handoff",
    "status": "ok",
    "timestamp": "2026-06-10T12:00:05Z",
    "from_agent": "company_sourcing",
    "to_agent": "problem_discovery",
    "payload_keys": ["company_record", "company_sources", "user_profile"],
    "reason": "Extract real technical problems from public signal."
}
```

### Checkup Gate Event (not persisted in trace_events; part of run record)

```python
{
    "decision": "pass",               # pass | retry | block | ask
    "stage": "problem_discovery",     # which stage the gate applied to
    "reason": "All metrics above threshold",
    "retry_count": 0,
    "overall_score": 8.2
}
```

## 4. State Ownership

| State | Current Owner | Target Owner | Storage |
|-------|---------------|-------------|---------|
| Run existence | Emergent | `orchestrator_service` | `run_records` table |
| Steps completed | Implicit (pipeline order) | `orchestrator_service` | `run_records.current_step` + `steps_completed` |
| Trace events | In-memory list | `orchestrator_service` | `trace_events` table |
| Retry counts | In-memory dict | `orchestrator_service` | `retry_counts` field on run record |
| Packet data | DB (packets table) | `orchestrator_service` | `packets` table (unchanged) |
| Approval records | `db.py` | `db.py` | `approvals` table (unchanged) |
| Send events | `db.py` | `db.py` | `send_events` table (unchanged) |
| Follow-ups | `db.py` | `db.py` | `follow_ups` table (unchanged) |
| W&B metrics | `RunLogger` | `RunLogger` | W&B + JSONL (unchanged) |
| Profile proof | `profile_harness` | `profile_harness` | `.upsearch/profile-harness-report.json` (unchanged) |

## 5. Recovery Protocol

When `server.py` starts after an abnormal shutdown:

1. Query `run_records WHERE status='running'`
2. For each abandoned run, mark `status = 'failed'` with error_message `"Server restarted while running"`
3. Return abandoned runs to the UI as "interrupted" with a retry button
4. Existing completed data in `packets`, `messages`, etc. is untouched

## 6. SSE Event Format (unchanged surface, extended)

The SSE contract from `server.py` to the frontend stays the same, with one new
event type:

| Event | Direction | Purpose |
|-------|-----------|---------|
| `stage` | server → client | Step status update |
| `log` | server → client | Agent log message |
| `gate` | server → client | Checkup retry notification |
| `block` | server → client | Pipeline blocked, needs review |
| `checkup` | server → client | Full checkup result |
| `complete` | server → client | Pipeline finished |
| `error` | server → client | Pipeline error |
| `keepalive` | server → client | **New**: 15s heartbeat to prevent proxy timeout |
| `progress` | server → client | **New**: step completion with trace event |

The `progress` event carries the trace event payload so the frontend can display
agent-step details in real time without polling.
