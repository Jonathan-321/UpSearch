"""Integration tests for scheduler using the shared orchestrator service.

These tests verify that ``execute_run_pipeline`` delegates to
``orchestrator_service.run_pipeline`` and correctly maps the result.
No network, no real agents — all calls are faked.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import run_scheduler as scheduler
import db
from upsearch import runtime
from upsearch.orchestrator_service import RunResult


# ── Helper factories ────────────────────────────────────────────────────────────


def _make_result(
    status: str = "complete",
    company: str = "AcmeCorp",
    lane: str = "ai_infra",
) -> RunResult:
    return RunResult(
        run_id="test-run-id",
        company_name=company,
        lane=lane,
        status=status,
        qa_result={"passed": status == "complete", "score": 8.5, "flags": []},
        profile={"name": "Test User"},
        company_record={"name": company, "fit_score": 8},
        problems=[{"title": "Inference latency"}],
        people=[{"name": "Alice", "role": "Engineer"}],
        technical_note_text="Technical analysis text. " * 30,
        outreach_drafts={"email": "Hello", "linkedin_note": "Hi"},
        packet_id=42,
    )


# ── Fixtures ────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_profile(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Create a temporary profile.txt for the scheduler to read."""
    profile_path = tmp_path / "profile.txt"
    profile_path.write_text("Test user with SWE background", encoding="utf-8")

    # Temporarily chdir so Path("profile.txt") resolves inside tmp_path
    origin = Path.cwd()
    monkeypatch.chdir(tmp_path)
    yield profile_path
    monkeypatch.chdir(origin)


# ── Tests ───────────────────────────────────────────────────────────────────────


def test_execute_run_pipeline_calls_orchestrator_service(fake_profile: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify execute_run_pipeline delegates to orchestrator_service.run_pipeline."""
    call_kwargs: dict = {}

    async def fake_run_pipeline(**kwargs):
        call_kwargs.update(kwargs)
        return _make_result()

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    result = scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp",
        "lane": "ai_infra",
        "source_urls": ["https://example.com"],
    })

    assert call_kwargs.get("company_name") == "AcmeCorp"
    assert call_kwargs.get("lane") == "ai_infra"
    assert call_kwargs.get("discovery_source_urls") == ["https://example.com"]
    assert isinstance(call_kwargs.get("profile_text"), str)
    assert len(call_kwargs["profile_text"]) > 0

    assert result.status == "processed"
    assert result.send_ready is True


def test_execute_run_pipeline_maps_complete_to_processed(fake_profile: Path, monkeypatch: pytest.MonkeyPatch):
    """A 'complete' pipeline result maps to JobResult(status='processed', send_ready=True)."""
    async def fake_run_pipeline(**kwargs):
        return _make_result(status="complete")

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    result = scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp", "lane": "ai_infra",
    })

    assert result.status == "processed"
    assert result.send_ready is True
    assert result.error is None


def test_execute_run_pipeline_maps_blocked_to_blocked(fake_profile: Path, monkeypatch: pytest.MonkeyPatch):
    """A 'blocked' pipeline result maps to JobResult(status='blocked')."""
    async def fake_run_pipeline(**kwargs):
        return RunResult(
            run_id="test-blocked",
            company_name="AcmeCorp",
            lane="ai_infra",
            status="blocked",
            qa_result={"passed": False, "score": 0, "flags": ["identity_blocked: no identity"]},
        )

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    result = scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp", "lane": "ai_infra",
    })

    assert result.status == "blocked"
    assert result.error is not None


def test_execute_run_pipeline_catches_exception(fake_profile: Path, monkeypatch: pytest.MonkeyPatch):
    """An exception from run_pipeline maps to JobResult(status='operational_exception')."""
    async def fake_run_pipeline(**kwargs):
        raise RuntimeError("Connection timeout")

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    result = scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp", "lane": "ai_infra",
    })

    assert result.status == "operational_exception"
    assert "Connection timeout" in (result.error or "")


def test_execute_run_pipeline_no_company_name(monkeypatch: pytest.MonkeyPatch):
    """Missing company_name returns blocked immediately without calling run_pipeline."""
    called = False

    async def fake_run_pipeline(**kwargs):
        nonlocal called
        called = True
        return _make_result()

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    result = scheduler.execute_run_pipeline({
        "company_name": "", "lane": "ai_infra",
    })

    assert result.status == "blocked"
    assert "No company_name" in (result.error or "")
    assert called is False


def test_execute_run_pipeline_unknown_status(fake_profile: Path, monkeypatch: pytest.MonkeyPatch):
    """An unexpected pipeline status maps to operational_exception."""
    async def fake_run_pipeline(**kwargs):
        return _make_result(status="unknown")

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    result = scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp", "lane": "ai_infra",
    })

    assert result.status == "operational_exception"
    assert "unknown" in (result.error or "")


def test_execute_run_pipeline_passes_profile_text(fake_profile: Path, monkeypatch: pytest.MonkeyPatch):
    """Verify the raw profile text read from disk is passed to run_pipeline."""
    profile_text_received = ""

    async def fake_run_pipeline(**kwargs):
        nonlocal profile_text_received
        profile_text_received = kwargs.get("profile_text", "")
        return _make_result()

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp", "lane": "ai_infra",
    })

    assert "Test user with SWE background" in profile_text_received


def test_execute_job_reuses_scheduler_job_id_as_run_lineage(
    fake_profile: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    """Operational retries of one scheduled job reuse the same run lineage."""
    run_ids: list[str] = []

    async def fake_run_pipeline(**kwargs):
        run_ids.append(kwargs["run_id"])
        return _make_result()

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)
    job = {
        "id": 73,
        "job_type": "run_pipeline",
        "lane": "ai_infra",
        "params": '{"company_name": "AcmeCorp", "lane": "ai_infra"}',
    }

    scheduler.execute_job(job)
    scheduler.execute_job(job)

    assert run_ids == ["scheduler-job-73", "scheduler-job-73"]


def test_recovery_requeues_interrupted_job_without_duplication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    """Restart recovery requeues the same persisted job instead of cloning it."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "scheduler.db")
    db.init_db()
    job_id = db.enqueue_job(
        "run_pipeline",
        params={"company_name": "AcmeCorp", "lane": "ai_infra"},
        lane="ai_infra",
    )
    claimed = db.dequeue_next_job()
    assert claimed and claimed["id"] == job_id

    assert runtime.recover_interrupted_jobs() == 1

    resumed = db.dequeue_next_job()
    assert resumed and resumed["id"] == job_id
    with db.conn() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM scheduled_jobs"
        ).fetchone()[0]
    assert count == 1


def test_execute_run_pipeline_empty_profile(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """When profile.txt is empty or missing, execute_run_pipeline still calls run_pipeline."""
    origin = Path.cwd()
    monkeypatch.chdir(tmp_path)
    # No profile.txt in tmp_path

    profile_text_received = ""

    async def fake_run_pipeline(**kwargs):
        nonlocal profile_text_received
        profile_text_received = kwargs.get("profile_text", "")
        return _make_result()

    monkeypatch.setattr(scheduler.orchestrator_service, "run_pipeline", fake_run_pipeline)

    scheduler.execute_run_pipeline({
        "company_name": "AcmeCorp", "lane": "ai_infra",
    })

    assert profile_text_received == ""
    monkeypatch.chdir(origin)
