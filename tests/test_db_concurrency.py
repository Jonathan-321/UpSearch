"""Concurrency guarantees for the SQLite job queue.

Two regressions are covered:

1. conn() must enable WAL + a busy timeout so the API server and the background
   worker can write at the same time without "database is locked".
2. dequeue_next_job() must claim each queued job exactly once even when many
   workers race for the same row.
"""
from __future__ import annotations

import threading
from collections import Counter

import db


def _seed_jobs(n: int) -> set[int]:
    return {db.enqueue_job("run_pipeline", params={"i": i}) for i in range(n)}


def test_conn_enables_wal_and_busy_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "wal.db")
    db.init_db()
    with db.conn() as c:
        journal_mode = c.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = c.execute("PRAGMA busy_timeout").fetchone()[0]
    assert journal_mode.lower() == "wal"
    assert busy_timeout >= 5000


def test_dequeue_claims_each_job_exactly_once_under_threads(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "queue.db")
    db.init_db()

    n_jobs = 60
    enqueued = _seed_jobs(n_jobs)

    n_workers = 12
    barrier = threading.Barrier(n_workers)
    claimed: list[int] = []
    claimed_lock = threading.Lock()

    def worker() -> None:
        # Release all threads at once to maximize contention on the queue.
        barrier.wait()
        while True:
            job = db.dequeue_next_job()
            if job is None:
                return
            with claimed_lock:
                claimed.append(job["id"])

    threads = [threading.Thread(target=worker) for _ in range(n_workers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert all(not t.is_alive() for t in threads), "a worker thread hung"

    counts = Counter(claimed)
    duplicates = {job_id: c for job_id, c in counts.items() if c > 1}
    assert not duplicates, f"jobs claimed more than once: {duplicates}"
    assert set(claimed) == enqueued
    assert len(claimed) == n_jobs


def test_dequeue_marks_job_running_and_keeps_dict_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "shape.db")
    db.init_db()
    job_id = db.enqueue_job("run_pipeline", params={"company": "Acme"}, lane="ai_infra")

    claimed = db.dequeue_next_job()
    assert claimed is not None
    assert claimed["id"] == job_id
    assert claimed["status"] == "running"
    assert claimed["started_at"] is not None
    # Same keys the SELECT-based row exposed: full scheduled_jobs schema.
    expected_keys = {
        "id", "job_type", "status", "params", "retry_count", "max_retries",
        "priority", "lane", "created_at", "started_at", "completed_at",
        "error_message",
    }
    assert set(claimed.keys()) == expected_keys

    # Queue is now empty.
    assert db.dequeue_next_job() is None
