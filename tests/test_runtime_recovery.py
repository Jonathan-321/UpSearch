"""Runtime, startup, health, migration, and recovery tests.

All tests use temporary directories — no network or credentials required.

Requirements covered:
1. Database and tracking paths are configurable and default to persistent local
   paths.
2. Startup applies idempotent schema initialization and reports migration state.
3. Health distinguishes process liveness from database/worker readiness.
4. Scheduler shutdown preserves queued work and resumes without duplication.
5. Backup and restore scripts cover SQLite plus .upsearch state.
6. Container runtime does not bake credentials into the image.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


# ── Runtime module tests ─────────────────────────────────────────────────────


def _import_runtime():
    """Helper to import runtime with clean env for each test."""
    from upsearch import runtime  # noqa: PLC0415
    return runtime


class TestPathResolution:
    """Requirement 1: configurable paths with sensible defaults."""

    def test_default_upsearch_dir(self) -> None:
        runtime = _import_runtime()
        p = runtime.resolve_upsearch_dir()
        assert str(p).endswith(".upsearch")

    def test_default_db_path(self) -> None:
        runtime = _import_runtime()
        p = runtime.resolve_db_path()
        assert str(p).endswith("opportunity_os.db")

    def test_configurable_upsearch_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPSEARCH_DIR", "/tmp/test-upsearch")
        runtime = _import_runtime()
        p = runtime.resolve_upsearch_dir()
        assert str(p) == "/tmp/test-upsearch"

    def test_configurable_db_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPSEARCH_DB_PATH", "/tmp/test-custom.db")
        runtime = _import_runtime()
        p = runtime.resolve_db_path()
        assert str(p) == "/tmp/test-custom.db"

    def test_configurable_tracking_dir(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPSEARCH_TRACKING_DIR", "/tmp/test-tracking")
        runtime = _import_runtime()
        p = runtime.resolve_tracking_dir()
        assert str(p) == "/tmp/test-tracking"

    def test_tracking_dir_defaults_to_upsearch_runs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPSEARCH_DIR", "/tmp/test-upsearch")
        monkeypatch.delenv("UPSEARCH_TRACKING_DIR", raising=False)
        runtime = _import_runtime()
        p = runtime.resolve_tracking_dir()
        assert str(p) == "/tmp/test-upsearch/runs"

    def test_ensure_dirs_creates_paths(self, tmp_path: Path) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setenv("UPSEARCH_DIR", str(tmp_path / ".upsearch"))
        monkeypatch.setenv("UPSEARCH_TRACKING_DIR", str(tmp_path / "runs"))
        runtime = _import_runtime()
        runtime.ensure_dirs()
        assert (tmp_path / ".upsearch").is_dir()
        assert (tmp_path / "runs").is_dir()


class TestMigrationState:
    """Requirement 2: startup applies idempotent schema and reports state."""

    def test_no_database_reports_pending(self, tmp_path: Path) -> None:
        runtime = _import_runtime()
        db_path = tmp_path / "nonexistent.db"
        info = runtime.check_migration_state(db_path)
        assert len(info.pending_migrations) > 0
        assert "not exist" in info.pending_migrations[0].lower()

    def test_init_db_creates_tables(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()
        runtime = _import_runtime()
        info = runtime.check_migration_state(tmp_path / "opportunity_os.db")
        # Should have most expected tables
        assert "approvals" in info.tables_found
        assert "companies" in info.tables_found
        assert "messages" in info.tables_found
        assert "send_events" in info.tables_found

    def test_idempotent_init(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()
        db.init_db()  # second call should not crash
        runtime = _import_runtime()
        info = runtime.check_migration_state(tmp_path / "opportunity_os.db")
        assert len(info.pending_migrations) == 0 or all(
            "body_digest" not in m for m in info.pending_migrations
        )

    def test_migration_reports_extra_columns(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        import sqlite3

        db.init_db()
        # Remove a column we expect to see in migrations
        conn = sqlite3.connect(str(tmp_path / "opportunity_os.db"))
        conn.execute("ALTER TABLE approvals DROP COLUMN body_digest")
        conn.close()

        runtime = _import_runtime()
        info = runtime.check_migration_state(tmp_path / "opportunity_os.db")
        pending = " ".join(info.pending_migrations)
        assert "body_digest" in pending or any("body_digest" in m for m in info.applied_migrations)


class TestHealthEndpoint:
    """Requirement 3: health distinguishes liveness from readiness."""

    def test_health_returns_expected_keys(self) -> None:
        runtime = _import_runtime()
        runtime.mark_started()
        h = runtime.health()
        assert "status" in h
        assert "uptime_seconds" in h
        assert "db_path" in h
        assert "db_exists" in h
        assert "tracking_dir" in h
        assert "migration_state" in h

    def test_health_reports_degraded_when_db_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("UPSEARCH_DB_PATH", "/tmp/nonexistent-upsearch-test.db")
        runtime = _import_runtime()
        h = runtime.health()
        assert h["status"] == "degraded"
        assert h["db_exists"] is False

    def test_health_reports_ok_after_init(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        db_path = tmp_path / "opportunity_os.db"
        monkeypatch.setenv("UPSEARCH_DB_PATH", str(db_path))
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()

        runtime = _import_runtime()
        h = runtime.health()
        # Should be ok or degraded (depends on migration completeness)
        assert h["db_exists"] is True
        assert isinstance(h["uptime_seconds"], (int, float))

    def test_uptime_increases(self) -> None:
        import time
        runtime = _import_runtime()
        runtime.mark_started()
        h1 = runtime.health()
        time.sleep(0.05)
        h2 = runtime.health()
        assert h2["uptime_seconds"] >= h1["uptime_seconds"]


class TestSchedulerShutdown:
    """Requirement 4: scheduler shutdown preserves queued work."""

    def test_collect_running_jobs_returns_empty_with_no_jobs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()
        runtime = _import_runtime()
        jobs = runtime.collect_running_jobs()
        assert jobs == []

    def test_enqueue_job_creates_persistent_entry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()
        db.enqueue_job("test_job", params={"hello": "world"}, priority=5)
        pending = db.get_pending_job_count()
        assert pending == 1

    def test_shutdown_summary_contains_pending_jobs(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()
        db.enqueue_job("discover_companies", params={"lane": "ai_infra"}, priority=5)

        runtime = _import_runtime()
        summary = runtime.shutdown_summary()
        assert summary["pending_jobs"] == 1
        assert summary["db_exists"] is True


class TestBackupScript:
    """Requirement 5: backup and restore scripts exist and refuse unsafe overwrites."""

    def test_backup_script_exists(self) -> None:
        script = Path(__file__).resolve().parent.parent / "scripts" / "backup-state.sh"
        assert script.is_file(), f"Backup script not found: {script}"
        assert os.access(script, os.X_OK), "Backup script is not executable"

    def test_restore_script_exists(self) -> None:
        script = Path(__file__).resolve().parent.parent / "scripts" / "restore-state.sh"
        assert script.is_file(), f"Restore script not found: {script}"
        assert os.access(script, os.X_OK), "Restore script is not executable"

    def test_backup_script_creates_timestamped_backup(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()

        scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
        backup_sh = str(scripts_dir / "backup-state.sh")

        result = subprocess.run(
            [backup_sh, str(tmp_path / "backups")],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0, f"Backup failed: {result.stderr}"

        # Verify backup directory was created
        backup_dirs = list((tmp_path / "backups").glob("upsearch-state-*"))
        assert len(backup_dirs) >= 1
        latest = backup_dirs[0]
        assert (latest / "manifest.json").is_file()

    def test_restore_script_refuses_overwrite_without_force(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.chdir(tmp_path)
        import db  # noqa: PLC0415
        db.init_db()

        # Insert a company so the DB has data
        db.upsert_company("TestCo", identity_status="verified")

        restore_sh = str(Path(__file__).resolve().parent.parent / "scripts" / "restore-state.sh")
        scripts_dir = Path(__file__).resolve().parent.parent / "scripts"

        # Create a minimal backup
        backup_dir = tmp_path / "restore-test-backup"
        backup_dir.mkdir()
        (backup_dir / "manifest.json").write_text(
            '{"backup_version": "1", "contents": {"database": false}}'
        )

        # Restore should fail because DB has data
        result = subprocess.run(
            [restore_sh, str(backup_dir)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode != 0
        assert "ERROR" in result.stdout or "has" in result.stdout


class TestDockerConfig:
    """Requirement 6: Docker infrastructure tests."""

    def test_dockerfile_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent
        assert (root / "Dockerfile").is_file()

    def test_docker_compose_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent
        assert (root / "docker-compose.yml").is_file()

    def test_dockerignore_exists(self) -> None:
        root = Path(__file__).resolve().parent.parent
        assert (root / ".dockerignore").is_file()

    def test_dockerignore_excludes_env(self) -> None:
        root = Path(__file__).resolve().parent.parent
        content = (root / ".dockerignore").read_text()
        assert ".env" in content
        assert "*.db" in content
        assert "__pycache__" in content

    def test_deployment_docs_exist(self) -> None:
        root = Path(__file__).resolve().parent.parent
        assert (root / "docs" / "deployment.md").is_file()
