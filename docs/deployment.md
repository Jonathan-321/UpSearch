# UpSearch Deployment Guide

UpSearch runs as a single Python service. All state is kept in a local SQLite
database plus the `.upsearch/` working directory. No external infrastructure
is required.

## Prerequisites

- Python 3.11+
- `uv` (recommended) or pip
- Docker (optional, for containerized deployment)
- API keys in `.env` (see `.env.example`)

## Quick Start (Local)

```bash
# 1. Install dependencies
uv sync

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Run the API server
uv run uvicorn server:app --host 0.0.0.0 --port 8000

# 4. Check health
curl http://localhost:8000/os/health
```

## Configuration

All configuration is through environment variables (see `.env.example`):

| Variable | Default | Description |
|---|---|---|
| `UPSEARCH_DIR` | `.upsearch` | Working directory for state files |
| `UPSEARCH_DB_PATH` | `opportunity_os.db` | SQLite database path |
| `UPSEARCH_TRACKING_DIR` | `<UPSEARCH_DIR>/runs` | Tracking/event logs |
| `UPSEARCH_STRONG_MODEL_PROVIDER` | `manual-review` | Provider for judgment tasks |
| `UPSEARCH_STRONG_MODEL` | `not-configured` | Model for judgment tasks |
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `ANTHROPIC_API_KEY` | — | Anthropic/Claude API key |
| `WANDB_API_KEY` | — | W&B API key (optional) |

## Database

The database is SQLite (`opportunity_os.db` by default). Schema is created and
migrated automatically on first startup via `db.init_db()`.

**Migration state** is reported through the health endpoint and the
`upsearch.runtime.check_migration_state()` function.

To inspect the database manually:

```bash
sqlite3 opportunity_os.db .tables
sqlite3 opportunity_os.db "SELECT COUNT(*) FROM companies"
```

## Health Endpoints

| Endpoint | Purpose |
|---|---|
| `GET /os/health` | Process liveness + DB readiness + migration state |
| `GET /api/health` | Legacy quick-search health |

The `/os/health` endpoint returns:

```json
{
  "status": "ok",
  "uptime_seconds": 123.4,
  "db_path": "/app/.upsearch/opportunity_os.db",
  "db_exists": true,
  "tracking_dir": "/app/.upsearch/runs",
  "migration_state": {
    "tables_found": ["approvals", "companies", "follow_ups", ...],
    "applied_migrations": ["Approvals: body_digest, channel, target"],
    "pending_migrations": []
  }
}
```

## Scheduler

The autonomous scheduler runs company discovery and packet generation:

```bash
# Run once (until queue empty)
python run_scheduler.py

# Run for 24 hours with automatic rediscovery
python run_scheduler.py --duration 24

# Test mode (2 jobs, 1 lane)
python run_scheduler.py --test --max-jobs 2
```

The scheduler persists queued work in the `scheduled_jobs` table. On shutdown
(at SIGINT/SIGTERM), running jobs are preserved — they are marked `running` in
the DB and the scheduler will resume them on the next start.

## Backup and Restore

```bash
# Create a timestamped backup
bash scripts/backup-state.sh

# Restore the latest backup
bash scripts/restore-state.sh

# Overwrite existing state
bash scripts/restore-state.sh --force

# Specify a path
bash scripts/restore-state.sh /path/to/specific/backup
```

Backups include:
- SQLite database (consistent snapshot via `VACUUM INTO`)
- `.upsearch/` directory (tracking, profile cache, reports)
- `profile.txt` (if present)

The restore script refuses to overwrite a non-empty database unless `--force`
is passed.

## Docker

### Build

```bash
docker build -t upsearch .
```

### Run

```bash
# With docker compose (recommended)
docker compose --env-file .env up -d

# Or manually
docker run -p 8000:8000 \
  -v upsearch_data:/app/.upsearch \
  --env-file .env \
  upsearch
```

*Credentials are never baked into the image.* Compose reads an optional local
`.env` only when supplied with `--env-file`; exported host environment
variables also work.

### Verify

```bash
curl http://localhost:8000/os/health
docker compose --env-file .env ps
docker compose --env-file .env logs -f
```

## Backup and Restore (Docker)

Backups work the same way inside Docker:

```bash
# Backup (mount the volume)
docker run --rm -v upsearch_data:/source \
  -v $(pwd)/backups:/dest \
  busybox cp -r /source/.upsearch /dest/
```

Or run the backup script on the host if the state directory is mounted as a
bind mount rather than a named volume.

## Upgrading

1. Pull the latest code: `git pull`
2. Rebuild the image: `docker compose build`
3. Restart: `docker compose --env-file .env up -d`

If there are schema migrations, `db.init_db()` applies them automatically
(idempotently) on startup. The migration state is visible in the health check.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---|---|---|
| Health shows `degraded` | DB missing or pending migrations | Run the API once — `init_db()` creates tables |
| `os/health` returns 404 | Wrong port or server not started | Check `docker compose ps` or `uv run` |
| `the database disk image is malformed` | Corrupt SQLite | Restore from backup, then run `PRAGMA integrity_check` |
| Scheduler exits immediately | Queue empty, `--once` mode | Use `--duration` to enable rediscovery |
| No new companies | API keys not configured | Check `.env` for valid keys |
