# Task 008: Deployment And Recovery Baseline

## Goal

Make UpSearch deployable as one small service with explicit health, persistent
state, migrations, restart behavior, and operator documentation.

## Read

- `server.py`, only app startup and health endpoints
- `db.py`, only connection, schema creation, and database path handling
- `run_scheduler.py`, only startup, shutdown, and queue persistence
- `pyproject.toml`
- `.env.example`

## Write Scope

- `upsearch/runtime.py` (new)
- `server.py`
- `db.py`
- `run_scheduler.py`
- `Dockerfile` (new)
- `docker-compose.yml` (new)
- `.dockerignore` (new)
- `scripts/backup-state.sh` (new)
- `scripts/restore-state.sh` (new)
- `docs/deployment.md` (new)
- `tests/test_runtime_recovery.py` (new)
- `.upsearch/agent-runs/008-deployment-recovery-handoff.md`

## Required Behavior

1. Database and tracking paths are configurable and default to persistent local
   paths.
2. Startup applies idempotent schema initialization and reports migration
   state.
3. Health distinguishes process liveness from database/worker readiness.
4. Scheduler shutdown preserves queued work and resumes without duplication.
5. Backup and restore scripts cover SQLite plus `.upsearch` state and refuse
   unsafe overwrites.
6. Container runtime does not bake credentials into the image.
7. Tests use temporary directories and require no network.

## Commands

```bash
uv run pytest -q tests/test_runtime_recovery.py
uv run pytest -q
docker compose config
git diff --check
```

If Docker is unavailable, record that verification gap in the handoff instead
of weakening the configuration.
