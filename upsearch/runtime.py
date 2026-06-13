"""
UpSearch Runtime — unified startup, health, path resolution, and migration state.

Everything needed to make UpSearch deployable as one small service:
- Configurable database and tracking paths with persistent defaults
- Idempotent schema initialization with migration reporting
- Health checks distinguishing process liveness from DB/worker readiness
- Graceful scheduler shutdown that preserves queued work
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_UPSEARCH_DIR = Path(".upsearch")
DEFAULT_DB_PATH = Path("opportunity_os.db")


# ── Path resolution ──────────────────────────────────────────────────────────


def resolve_upsearch_dir() -> Path:
    """Return the resolved .upsearch directory, defaulting to CWD/.upsearch."""
    raw = os.environ.get("UPSEARCH_DIR", "")
    return Path(raw) if raw else (Path.cwd() / ".upsearch")


def resolve_db_path() -> Path:
    """Return the resolved database path, defaulting to CWD/opportunity_os.db."""
    raw = os.environ.get("UPSEARCH_DB_PATH", "")
    return Path(raw) if raw else (Path.cwd() / "opportunity_os.db")


def resolve_tracking_dir() -> Path:
    """Return the resolved tracking directory."""
    raw = os.environ.get("UPSEARCH_TRACKING_DIR", "")
    return Path(raw) if raw else (resolve_upsearch_dir() / "runs")


def ensure_dirs() -> None:
    """Create all required directories."""
    resolve_upsearch_dir().mkdir(parents=True, exist_ok=True)
    resolve_tracking_dir().mkdir(parents=True, exist_ok=True)


# ── Migration reporting ──────────────────────────────────────────────────────


@dataclass
class MigrationInfo:
    """State of database migrations at startup."""
    schema_version: int = 0
    tables_found: list[str] = field(default_factory=list)
    applied_migrations: list[str] = field(default_factory=list)
    pending_migrations: list[str] = field(default_factory=list)
    migrations_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "tables_found": self.tables_found,
            "applied_migrations": self.applied_migrations,
            "pending_migrations": self.pending_migrations,
            "migrations_path": self.migrations_path,
        }


KNOWN_TABLES = frozenset({
    "user_profile", "companies", "problems", "people", "sources",
    "packets", "messages", "approvals", "send_events", "follow_ups",
    "run_records", "trace_events", "scheduled_jobs",
})


def check_migration_state(db_path: Path | str) -> MigrationInfo:
    """Inspect the database and return its migration state.

    This is a read-only operation — it does not modify the database.
    """
    import sqlite3

    p = Path(db_path)
    info = MigrationInfo(
        schema_version=0,
        migrations_path=str(p),
    )

    if not p.exists():
        info.pending_migrations = ["Database does not exist — will be created on first init"]
        return info

    try:
        conn = sqlite3.connect(str(p))
        conn.row_factory = sqlite3.Row
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        info.tables_found = [row["name"] for row in tables]

        present = set(info.tables_found)
        missing = KNOWN_TABLES - present
        if present & KNOWN_TABLES:
            info.schema_version = len(present & KNOWN_TABLES)
        if missing:
            info.pending_migrations = [f"Missing table: {t}" for t in sorted(missing)]

        # Check for migration-only columns
        approval_extra = {"body_digest", "channel", "target"}
        if "approvals" in present:
            cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(approvals)").fetchall()
            }
            missing_cols = approval_extra - cols
            if missing_cols:
                info.pending_migrations.append(
                    f"Approvals table needs columns: {', '.join(sorted(missing_cols))}"
                )
            else:
                info.applied_migrations.append("Approvals: body_digest, channel, target")

        if "send_events" in present:
            send_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(send_events)").fetchall()
            }
            send_extra = {"body_digest", "error_message"}
            missing_cols = send_extra - send_cols
            if missing_cols:
                info.pending_migrations.append(
                    f"Send events table needs columns: {', '.join(sorted(missing_cols))}"
                )
            else:
                info.applied_migrations.append("Send events: body_digest, error_message")

        if "follow_ups" in present:
            follow_up_cols = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(follow_ups)").fetchall()
            }
            follow_up_extra = {"approval_id", "body_digest", "created_at"}
            missing_cols = follow_up_extra - follow_up_cols
            if missing_cols:
                info.pending_migrations.append(
                    f"Follow-ups table needs columns: {', '.join(sorted(missing_cols))}"
                )
            else:
                info.applied_migrations.append(
                    "Follow-ups: approval_id, body_digest, created_at"
                )

        conn.close()
    except Exception as exc:
        info.pending_migrations.append(f"Error inspecting database: {exc}")

    return info


# ── Health ────────────────────────────────────────────────────────────────────


_HEALTH_START_TIME: float = 0.0


def mark_started() -> None:
    """Record the process start time for uptime calculation."""
    global _HEALTH_START_TIME  # noqa: PLW0603
    _HEALTH_START_TIME = time.monotonic()


def health() -> dict[str, Any]:
    """Return a health dict with liveness, readiness, and migration state.

    Returns:
        {
            "status": "ok" | "degraded" | "error",
            "uptime_seconds": ...,
            "db_path": ...,
            "db_exists": ...,
            "tracking_dir": ...,
            "migration_state": {...},
        }
    """
    db_path = resolve_db_path()
    tracking_dir = resolve_tracking_dir()

    info = check_migration_state(db_path)
    db_exists = db_path.exists()
    pending = bool(info.pending_migrations)
    status = "ok"
    if pending:
        status = "degraded"
    if not db_exists:
        status = "degraded"

    return {
        "status": status,
        "uptime_seconds": round(time.monotonic() - _HEALTH_START_TIME, 1) if _HEALTH_START_TIME else 0,
        "db_path": str(db_path),
        "db_exists": db_exists,
        "tracking_dir": str(tracking_dir),
        "migration_state": info.to_dict(),
    }


# ── Graceful shutdown ────────────────────────────────────────────────────────


def collect_running_jobs() -> list[dict[str, Any]]:
    """Return a list of jobs that were running at shutdown so the operator can
    inspect and resume them."""
    import db

    try:
        running = db.get_running_jobs()
        return [dict(j) for j in running]
    except Exception:
        return []


def recover_interrupted_jobs() -> int:
    """Requeue jobs left running by an interrupted scheduler process."""
    import db

    with db.conn() as connection:
        cursor = connection.execute(
            """UPDATE scheduled_jobs
               SET status='queued', started_at=NULL, completed_at=NULL
               WHERE status='running'"""
        )
        return cursor.rowcount


def shutdown_summary() -> dict[str, Any]:
    """Return a structured summary suitable for logging at shutdown."""
    import db

    up_dir = resolve_upsearch_dir()
    db_path = resolve_db_path()
    summary = {
        "upsearch_dir": str(up_dir),
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "tracking_dir": str(resolve_tracking_dir()),
    }
    try:
        summary["pending_jobs"] = db.get_pending_job_count()
        summary["running_jobs"] = len(collect_running_jobs())
        summary["companies_in_db"] = db.count_companies()
    except Exception:
        summary["pending_jobs"] = -1
        summary["running_jobs"] = -1

    return summary
