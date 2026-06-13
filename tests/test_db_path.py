"""Task 027: db.DB_PATH must follow upsearch.runtime.resolve_db_path().

The release-acceptance script exports UPSEARCH_DB_PATH at a temporary state
directory. Before this fix db.py hardcoded a relative path and ignored the
variable, so the "empty temporary state" steps silently ran against the real
repository database. Path resolution happens once at import, so the env-var
behavior is asserted in fresh interpreters.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import db

REPO_ROOT = Path(__file__).resolve().parents[1]


def _python(code: str, *, env: dict, cwd: Path) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def test_db_path_honors_upsearch_db_path_env(tmp_path):
    target = tmp_path / "custom" / "state.db"
    env = {**os.environ, "UPSEARCH_DB_PATH": str(target), "PYTHONPATH": str(REPO_ROOT)}
    out = _python("import db; print(db.DB_PATH)", env=env, cwd=REPO_ROOT)
    assert out == str(target)


def test_db_path_defaults_to_cwd_database(tmp_path):
    """Without the override the default stays CWD-relative per connection, so
    chdir-based tests (and any process started in a state dir) write locally,
    never into the repository database."""
    env = {k: v for k, v in os.environ.items() if k != "UPSEARCH_DB_PATH"}
    env["PYTHONPATH"] = str(REPO_ROOT)
    out = _python("import db; db.init_db(); print(db.DB_PATH)", env=env, cwd=tmp_path)
    assert Path(out) == Path("opportunity_os.db")
    assert (tmp_path / "opportunity_os.db").exists()


def test_runtime_imports_before_db_without_cycle():
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT)}
    out = _python(
        "import upsearch.runtime; import db; print('ok')", env=env, cwd=REPO_ROOT
    )
    assert out == "ok"


def test_monkeypatched_db_path_still_routes_connections(tmp_path, monkeypatch):
    """The existing test-suite pattern: setattr(db, 'DB_PATH', ...) keeps working."""
    target = tmp_path / "patched.db"
    monkeypatch.setattr(db, "DB_PATH", target)
    db.init_db()
    assert target.exists()
    with db.conn() as c:
        tables = {
            row["name"]
            for row in c.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert "people" in tables
