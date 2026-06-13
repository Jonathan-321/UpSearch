"""Deterministic unit tests for scheduler rediscovery logic (no network calls).

These tests monkey-patch db functions and time so the scheduler loop
is fully controlled — no real SQLite, no real discovery.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
import run_scheduler as scheduler
from upsearch.orchestrator_service import RunResult


# ── Fake DB Shim ─────────────────────────────────────────────────────────────


@dataclass
class FakeJob:
    id: int
    job_type: str
    params: dict
    lane: str = ""
    status: str = "queued"
    retry_count: int = 0
    max_retries: int = 2

    def as_row(self) -> dict:
        return {
            "id": self.id,
            "job_type": self.job_type,
            "params": json.dumps(self.params),
            "lane": self.lane,
            "status": self.status,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "started_at": None,
        }


class FakeDB:
    """In-memory mock of the db module used by run_scheduler.py."""

    def __init__(self) -> None:
        self._jobs: dict[int, FakeJob] = {}
        self._next_id = 1
        self._companies: set[str] = set()
        self._call_log: list[str] = []

    def clear(self) -> None:
        self._jobs.clear()
        self._next_id = 1
        self._companies.clear()
        self._call_log.clear()

    # ── Job API ──────────────────────────────────────────────────────────

    def enqueue_job(
        self,
        job_type: str,
        params: dict | None = None,
        lane: str | None = None,
        max_retries: int = 3,
        priority: int = 0,
    ) -> int:
        jid = self._next_id
        self._next_id += 1
        self._jobs[jid] = FakeJob(
            id=jid,
            job_type=job_type,
            params=params or {},
            lane=lane or "",
            max_retries=max_retries,
        )
        self._call_log.append(f"enqueue:{job_type} lane={lane}")
        return jid

    def dequeue_next_job(self) -> dict | None:
        for jid in sorted(self._jobs.keys()):
            j = self._jobs[jid]
            if j.status == "queued":
                j.status = "running"
                self._call_log.append(f"dequeue:{j.job_type} id={jid}")
                return j.as_row()
        return None

    def complete_job(self, job_id: int) -> None:
        if job_id in self._jobs:
            self._jobs[job_id].status = "complete"
            self._call_log.append(f"complete:{job_id}")

    def fail_job(self, job_id: int, error: str, retry: bool = True) -> str:
        if job_id not in self._jobs:
            return "gone"
        j = self._jobs[job_id]
        j.retry_count += 1
        if retry and j.retry_count <= j.max_retries:
            j.status = "queued"
            self._call_log.append(f"fail-retry:{job_id}")
            return "queued"
        j.status = "failed"
        self._call_log.append(f"fail-permanent:{job_id}")
        return "failed"

    def get_pending_job_count(self) -> int:
        return sum(
            1 for j in self._jobs.values() if j.status in ("queued", "running")
        )

    def get_job_summary(self) -> list[dict]:
        return [{"id": j.id, "status": j.status} for j in self._jobs.values()]

    def has_pending_discovery_for_lane(self, lane: str) -> bool:
        return any(
            j.job_type == "discover_companies"
            and j.status in ("queued", "running")
            and j.params.get("lane") == lane
            for j in self._jobs.values()
        )

    def has_pending_refresh(self) -> bool:
        return any(
            j.job_type == "refresh_profile" and j.status in ("queued", "running")
            for j in self._jobs.values()
        )


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def fakedb() -> FakeDB:
    return FakeDB()


@pytest.fixture
def wired_scheduler(monkeypatch: pytest.MonkeyPatch, fakedb: FakeDB) -> FakeDB:
    monkeypatch.setattr(scheduler.db, "enqueue_job", fakedb.enqueue_job)
    monkeypatch.setattr(scheduler.db, "get_pending_job_count", fakedb.get_pending_job_count)
    monkeypatch.setattr(
        scheduler,
        "_has_pending_discovery_for_lane",
        fakedb.has_pending_discovery_for_lane,
    )
    monkeypatch.setattr(scheduler, "_has_pending_refresh", fakedb.has_pending_refresh)
    return fakedb


# ── Unit Tests ───────────────────────────────────────────────────────────────


class TestEnqueueRediscovery:
    """Tests for the _enqueue_rediscovery helper that drives rediscovery."""

    def test_enqueues_discovery_for_all_lanes(self, wired_scheduler: FakeDB) -> None:
        """Should enqueue one discovery job per lane."""
        fakedb = wired_scheduler
        scheduler._enqueue_rediscovery(["ai_infra", "agentic_ai"], max_companies=5)

        discovery_calls = [
            call for call in fakedb._call_log if "enqueue:discover_companies" in call
        ]
        assert len(discovery_calls) == 2
        assert "lane=ai_infra" in discovery_calls[0]
        assert "lane=agentic_ai" in discovery_calls[1]

    def test_skips_lane_with_pending_discovery(self, wired_scheduler: FakeDB) -> None:
        """When a lane already has a queued discovery job, don't enqueue another."""
        fakedb = wired_scheduler
        initial_count = len(fakedb._call_log)
        fakedb.enqueue_job(
            "discover_companies",
            params={"lane": "ai_infra", "max_candidates": 5},
            lane="ai_infra",
        )
        scheduler._enqueue_rediscovery(["ai_infra", "inference_systems"])

        # Calls made only during the rediscovery call
        rediscovery_calls = fakedb._call_log[initial_count + 1:]
        discovery_calls = [
            call for call in rediscovery_calls if "enqueue:discover_companies" in call
        ]
        # Only inference_systems should be enqueued (ai_infra was skipped)
        assert len(discovery_calls) == 1
        assert "inference_systems" in discovery_calls[0]
        # Ensure ai_infra was NOT re-enqueued
        assert not any("ai_infra" in c for c in discovery_calls)

    def test_enqueues_profile_refresh_when_none_pending(self, wired_scheduler: FakeDB) -> None:
        """Should enqueue one refresh_profile when none is already queued."""
        fakedb = wired_scheduler
        scheduler._enqueue_rediscovery(["ai_infra"])

        refresh_calls = [
            call for call in fakedb._call_log if "enqueue:refresh_profile" in call
        ]
        assert len(refresh_calls) == 1

    def test_skips_profile_refresh_when_pending(self, wired_scheduler: FakeDB) -> None:
        """Should NOT enqueue a second refresh_profile when one is already pending."""
        fakedb = wired_scheduler
        fakedb.enqueue_job("refresh_profile", lane="", max_retries=1)
        scheduler._enqueue_rediscovery(["ai_infra"])

        refresh_calls = [
            call for call in fakedb._call_log if "enqueue:refresh_profile" in call
        ]
        # Only the initial enqueue, not from rediscovery
        assert len(refresh_calls) == 1

    def test_enqueue_after_pending_completes(self, wired_scheduler: FakeDB) -> None:
        """After a pending discovery completes, rediscovery should enqueue new ones."""
        fakedb = wired_scheduler
        initial_count = len(fakedb._call_log)
        # Seed a pending discovery
        jid = fakedb.enqueue_job(
            "discover_companies",
            params={"lane": "ai_infra", "max_candidates": 5},
            lane="ai_infra",
        )
        fakedb.complete_job(jid)
        assert fakedb.get_pending_job_count() == 0

        scheduler._enqueue_rediscovery(["ai_infra", "agentic_ai"])

        # Calls made only during rediscovery
        rediscovery_calls = fakedb._call_log[initial_count + 2:]
        discovery_calls = [
            call for call in rediscovery_calls if "enqueue:discover_companies" in call
        ]
        # Both lanes should be enqueued since the old one completed
        assert len(discovery_calls) == 2


class TestInitialEnqueue:
    def test_enqueues_exactly_one_profile_refresh(
        self,
        wired_scheduler: FakeDB,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(scheduler, "source_cache_is_fresh", lambda: False)

        scheduler.enqueue_initial_tasks(["ai_infra", "agentic_ai"], max_companies=3)

        refresh_calls = [
            call for call in wired_scheduler._call_log
            if "enqueue:refresh_profile" in call
        ]
        discovery_calls = [
            call for call in wired_scheduler._call_log
            if "enqueue:discover_companies" in call
        ]
        assert len(refresh_calls) == 1
        assert len(discovery_calls) == 2


class TestSchedulerLoopLogic:
    """Deterministic tests of the scheduler main-loop decisions.

    We test the decision logic directly rather than calling main()
    with fake time, which is fragile.
    """

    def test_once_mode_exits_when_empty(self, wired_scheduler: FakeDB) -> None:
        """In --once mode (duration=0), exit immediately when queue is empty."""
        fakedb = wired_scheduler
        # Empty queue
        assert fakedb.get_pending_job_count() == 0

        decision = scheduler._loop_decision(
            once_mode=True,
            deadline=float("inf"),
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=0,
            max_idle_cycles=None,
            now=0,
        )
        assert decision["action"] == "exit"
        assert "drained" in decision["reason"]

    def test_duration_mode_waits_and_rediscovers(self, wired_scheduler: FakeDB) -> None:
        """With --duration > 0 and empty queue, decision requests rediscovery."""
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=float("inf"),
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=0,
            max_idle_cycles=None,
            now=0,
        )
        assert decision["action"] == "idle_rediscover"
        assert "idle" in decision["reason"].lower()

    def test_duration_mode_exits_on_deadline(self, wired_scheduler: FakeDB) -> None:
        """Even in duration mode, exit when deadline has passed."""
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=0.0,  # past deadline immediately
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=0,
            max_idle_cycles=None,
            now=1,
        )
        assert decision["action"] == "exit"
        assert "deadline" in decision["reason"]

    def test_exits_after_max_idle_cycles(self, wired_scheduler: FakeDB) -> None:
        """When max_idle_cycles is reached, exit even in duration mode."""
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=float("inf"),
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=5,
            max_idle_cycles=5,
            now=0,
        )
        assert decision["action"] == "exit"
        assert "idle cycle" in decision["reason"].lower()

    def test_exits_after_max_jobs(self, wired_scheduler: FakeDB) -> None:
        """max_jobs check should still apply."""
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=float("inf"),
            max_jobs=10,
            total_processed=10,
            idle_cycle_count=0,
            max_idle_cycles=None,
            now=0,
        )
        assert decision["action"] == "exit"
        assert "max jobs" in decision["reason"]

    def test_waits_when_queued_job_is_present(self, wired_scheduler: FakeDB) -> None:
        """The empty-queue decision must not rediscover while work is pending."""
        fakedb = wired_scheduler
        fakedb.enqueue_job("run_pipeline", params={"company_name": "Acme"}, lane="ai_infra")
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=float("inf"),
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=0,
            max_idle_cycles=None,
            now=0,
        )
        assert decision["action"] == "wait"
        assert "queued/running" in decision["reason"]

    def test_waits_for_running_jobs(self, wired_scheduler: FakeDB) -> None:
        """When pending jobs exist (running), wait, don't exit or rediscover."""
        fakedb = wired_scheduler
        jid = fakedb.enqueue_job("run_pipeline", params={"company_name": "Acme"}, lane="ai_infra")
        fakedb._jobs[jid].status = "running"
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=float("inf"),
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=0,
            max_idle_cycles=None,
            now=0,
        )
        assert decision["action"] == "wait"
        assert "running" in decision["reason"].lower()

    def test_increments_idle_counter(self, wired_scheduler: FakeDB) -> None:
        """Each empty-queue wait in duration mode increments the idle cycle counter."""
        decision = scheduler._loop_decision(
            once_mode=False,
            deadline=float("inf"),
            max_jobs=0,
            total_processed=0,
            idle_cycle_count=3,
            max_idle_cycles=5,
            now=0,
        )
        assert decision["action"] == "idle_rediscover"
        assert decision.get("next_idle_cycle") == 4


class TestIdentityIntegration:
    def test_discovery_persists_identity_and_sources(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidate = SimpleNamespace(
            name="Example AI",
            canonical_name="Example AI, Inc.",
            website="https://example.ai",
            official_domain="example.ai",
            identity_status="verified",
            identity_confidence=0.93,
            identity_reason="Official domain matched the company launch source.",
            fit_guess=0.8,
            source_urls=["https://news.ycombinator.com/item?id=123"],
            evidence=["Show HN: Example AI"],
        )
        upserts: list[tuple[str, dict]] = []
        sources: list[tuple[str, dict]] = []
        jobs: list[tuple[str, dict]] = []

        monkeypatch.setattr(scheduler, "discover", lambda lane, limit: [candidate])
        monkeypatch.setattr(scheduler.db, "get_company", lambda name: None)
        monkeypatch.setattr(
            scheduler.db,
            "upsert_company",
            lambda name, **fields: upserts.append((name, fields)) or 17,
        )
        monkeypatch.setattr(
            scheduler.db,
            "insert_source",
            lambda url, **fields: sources.append((url, fields)) or 31,
        )
        monkeypatch.setattr(scheduler, "check_company_has_pending_job", lambda name: False)
        monkeypatch.setattr(
            scheduler.db,
            "enqueue_job",
            lambda job_type, **fields: jobs.append((job_type, fields)) or 41,
        )

        result = scheduler.execute_discover_companies(
            {"lane": "ai_infra", "max_candidates": 2}
        )

        assert result.status == "processed"
        assert upserts == [
            (
                "Example AI",
                {
                    "canonical_name": "Example AI, Inc.",
                    "website": "https://example.ai",
                    "official_domain": "example.ai",
                    "identity_status": "verified",
                    "identity_confidence": 0.93,
                    "identity_reason": "Official domain matched the company launch source.",
                    "lane": "ai_infra",
                    "fit_score": 8.0,
                    "source_urls": json.dumps(candidate.source_urls),
                    "status": "sourced",
                },
            )
        ]
        assert sources[0][0] == candidate.source_urls[0]
        assert sources[0][1]["claim_type"] == "company_identity"
        assert sources[0][1]["verified"] is True
        assert jobs[0][0] == "run_pipeline"
        assert jobs[0][1]["params"]["source_urls"] == candidate.source_urls

    def test_pipeline_blocks_unverified_identity_before_generation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When orchestrator returns blocked status, scheduler maps to JobResult."""
        pipeline_calls: list[dict] = []

        async def fake_run_pipeline(**kwargs):
            pipeline_calls.append(kwargs)
            return RunResult(
                run_id="test-blocked",
                company_name=kwargs.get("company_name", ""),
                lane=kwargs.get("lane", ""),
                status="blocked",
                qa_result={
                    "passed": False,
                    "score": 0,
                    "flags": ["identity_blocked: No official domain evidence."],
                },
            )

        monkeypatch.setattr(
            scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline
        )

        discovery_urls = ["https://news.ycombinator.com/item?id=456"]
        result = scheduler.execute_run_pipeline(
            {
                "company_name": "Unverified Co",
                "lane": "ai_infra",
                "source_urls": discovery_urls,
            }
        )

        assert len(pipeline_calls) == 1
        assert pipeline_calls[0]["company_name"] == "Unverified Co"
        assert pipeline_calls[0]["lane"] == "ai_infra"
        assert pipeline_calls[0]["discovery_source_urls"] == discovery_urls

        assert result.status == "blocked"
        assert "identity_blocked" in (result.error or "")
