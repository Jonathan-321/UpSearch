"""Tests for orchestrator_service.run_pipeline with fake agents and temp SQLite.

Every test uses temporary databases and fake agent stubs so no network,
credentials, or real LLM calls are involved.
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

import pytest

import db
from agents import company, outreach, people, problem, profile, qa, technical_note
from upsearch.orchestrator_service import run_pipeline


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch):
    """Replace the database path with a temporary file."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    yield tmp_path / "test.db"


# ── Stub factories ────────────────────────────────────────────────────────────


def _stub_profile(**overrides) -> dict:
    data = {
        "name": "Test User",
        "school": "Test University",
        "background": "SWE intern at BigCo",
    }
    data.update(overrides)
    return data


def _stub_company(**overrides) -> dict:
    data = {
        "result": {
            "name": "AcmeCorp",
            "website": "https://acme.example.com",
            "official_domain": "acme.example.com",
            "identity_status": "verified",
            "identity_confidence": 0.9,
            "fit_score": 8,
            "hiring_status": "hiring",
            "what_they_do": "AI infrastructure",
            "why": "Strong hiring signal in infra",
        },
        "source_urls": ["https://acme.example.com/about"],
    }
    data.update(overrides)
    return data


def _stub_problems(**overrides) -> dict:
    data = {
        "result": {
            "problems": [
                {
                    "title": "Inference latency at scale",
                    "description": "High tail latency for LLM inference",
                    "source_urls": ["https://news.ycombinator.com/item?id=1"],
                    "relevance_score": 8,
                },
            ],
        },
        "source_urls": ["https://news.ycombinator.com/item?id=1"],
    }
    data.update(overrides)
    return data


def _stub_people(**overrides) -> dict:
    data = {
        "result": {
            "people": [
                {
                    "name": "Alice Engineer",
                    "role": "Staff Engineer",
                    "linkedin_url": "https://linkedin.com/in/alice",
                    "source_url": "https://github.com/alice",
                    "verification_status": "verified",
                    "relevance_score": 9,
                    "relevance_reason": "Works on inference",
                    "proximity": "engineer",
                },
            ],
        },
        "source_urls": ["https://github.com/alice"],
    }
    data.update(overrides)
    return data


def _stub_note(**overrides) -> dict:
    data = {
        "result": {
            "technical_note": " ".join(
                ["Technical analysis of inference latency at AcmeCorp."] * 45
            ),
            "adjacent_proof": "https://blog.acme.example.com/inference-optimization",
        },
    }
    data.update(overrides)
    return data


def _stub_outreach(**overrides) -> dict:
    data = {
        "result": {
            "email": "Hi Alice, I noticed your work on inference at AcmeCorp...",
            "linkedin_note": "Hi Alice, great work on inference at AcmeCorp...",
        },
    }
    data.update(overrides)
    return data


def _stub_qa(**overrides) -> dict:
    data = {"score": 8.5, "passed": True, "flags": []}
    data.update(overrides)
    return data


def _install_stubs(monkeypatch: pytest.MonkeyPatch):
    """Replace the agent module entry points imported by run_pipeline."""
    monkeypatch.setattr(profile, "run", lambda e: _stub_profile())
    monkeypatch.setattr(company, "run", lambda n, l, p: _stub_company())
    monkeypatch.setattr(problem, "run", lambda n, c, p: _stub_problems())
    monkeypatch.setattr(
        people,
        "run",
        lambda n, pb, pf, company_domain="": _stub_people(),
    )
    monkeypatch.setattr(
        technical_note,
        "run",
        lambda n, c, pb, pf: _stub_note(),
    )
    monkeypatch.setattr(
        outreach,
        "run",
        lambda n, pb, pn, nt, ap, pf: _stub_outreach(),
    )
    monkeypatch.setattr(qa, "run", lambda pkt, pf: _stub_qa())


# ── Tests ─────────────────────────────────────────────────────────────────────


def test_run_pipeline_happy_path(tmp_db, monkeypatch):
    """Verify the full pipeline runs end-to-end with fake agent returns.

    All 7 agents run in order, DB rows are written, and a run record is
    created with 'complete' status.
    """
    _install_stubs(monkeypatch)

    events: list[tuple[str, dict]] = []

    def on_event(event_type: str, data: dict):
        events.append((event_type, data))

    result = asyncio.run(
        run_pipeline(
            "AcmeCorp",
            "ai_infra",
            "Test user profile text",
            progress_callback=on_event,
        )
    )

    # ── Assert run record ─────────────────────────────────────────────────────
    assert isinstance(result.run_id, str) and len(result.run_id) > 0
    record = db.get_run_record(result.run_id)
    assert record is not None
    assert record["status"] == "complete"
    assert record["company_name"] == "AcmeCorp"
    assert record["lane"] == "ai_infra"
    assert result.status == "complete"

    # ── Assert profile result ─────────────────────────────────────────────────
    assert result.profile["name"] == "Test User"
    assert result.profile["school"] == "Test University"

    # ── Assert company result ─────────────────────────────────────────────────
    assert result.company_record["name"] == "AcmeCorp"
    assert result.company_record["fit_score"] == 8

    # ── Assert problems ─────────────────────────────────────────────────────
    assert len(result.problems) == 1
    assert result.problems[0]["title"] == "Inference latency at scale"

    # ── Assert people ─────────────────────────────────────────────────────────
    assert len(result.people) == 1
    assert result.people[0]["name"] == "Alice Engineer"

    # ── Assert technical note ─────────────────────────────────────────────────
    assert "Technical analysis" in result.technical_note_text

    # ── Assert outreach ───────────────────────────────────────────────────────
    assert "email" in result.outreach_drafts
    assert "linkedin_note" in result.outreach_drafts

    # ── Assert QA ─────────────────────────────────────────────────────────────
    assert result.qa_result["score"] == 8.5
    assert result.qa_result["passed"] is True

    # ── Assert DB persistence ─────────────────────────────────────────────────
    company = db.get_company("AcmeCorp")
    assert company is not None
    assert company["fit_score"] == 8

    stored_problems = db.get_problems(result.db_company_id)
    assert len(stored_problems) == 1

    stored_people = db.get_people(result.db_company_id)
    assert len(stored_people) == 1

    packet = db.get_packet(result.db_company_id)
    assert packet is not None
    assert packet["qa_score"] == 8.5

    # ── Assert progress events ────────────────────────────────────────────────
    event_types = [e[0] for e in events]
    assert "stage" in event_types
    assert "log" in event_types
    assert "complete" in event_types

    # Verify agent order in stages
    stage_names = [e[1].get("stage") for e in events if e[0] == "stage"]
    assert "profile" in stage_names
    assert "company" in stage_names
    assert "problem" in stage_names
    assert "people" in stage_names
    assert "technical_note" in stage_names
    assert "outreach" in stage_names
    assert "qa" in stage_names


def test_run_pipeline_creates_run_record(tmp_db, monkeypatch):
    """Verify a run record is created and tracks the execution lifecycle."""
    _install_stubs(monkeypatch)
    result = asyncio.run(run_pipeline("AcmeCorp", "ai_infra", "profile text"))

    record = db.get_run_record(result.run_id)
    assert record is not None
    assert record["run_id"] == result.run_id
    assert record["status"] == "complete"
    assert record["company_name"] == "AcmeCorp"
    assert record["started_at"] is not None
    assert record["completed_at"] is not None

    steps = record.get("steps_completed", [])
    assert "company" in steps
    assert "problem" in steps
    assert "people" in steps
    assert "qa" in steps


def test_run_pipeline_propagates_run_id_in_events(tmp_db, monkeypatch):
    """Verify the run_id is set on every progress event."""
    _install_stubs(monkeypatch)

    events: list[tuple[str, dict]] = []

    def on_event(event_type: str, data: dict):
        events.append((event_type, data))

    result = asyncio.run(
        run_pipeline(
            "AcmeCorp",
            "ai_infra",
            "profile text",
            progress_callback=on_event,
        )
    )

    assert len(events) > 0
    for event_type, data in events:
        assert "run_id" in data, f"Event {event_type} missing run_id"
        assert data["run_id"] == result.run_id


def test_run_pipeline_result_contains_run_id(tmp_db, monkeypatch):
    """RunResult always has the run_id matching the DB record."""
    _install_stubs(monkeypatch)
    result = asyncio.run(run_pipeline("AcmeCorp", "ai_infra", "profile"))

    assert isinstance(result.run_id, str)
    assert len(result.run_id) > 0
    assert result.company_name == "AcmeCorp"
    assert result.lane == "ai_infra"

    record = db.get_run_record(result.run_id)
    assert record is not None


def test_identity_block_emits_terminal_complete_event(tmp_db, monkeypatch):
    _install_stubs(monkeypatch)
    monkeypatch.setattr(
        company,
        "run",
        lambda n, l, p: _stub_company(
            result={
                "name": n,
                "identity_status": "rejected",
                "identity_reason": "No verified official domain.",
                "fit_score": 7,
            }
        ),
    )
    events: list[tuple[str, dict]] = []

    result = asyncio.run(
        run_pipeline(
            "UnverifiedCo",
            "ai_infra",
            "profile",
            progress_callback=lambda event_type, data: events.append((event_type, data)),
        )
    )

    assert result.status == "blocked"
    terminal = [data for event_type, data in events if event_type == "complete"]
    assert terminal == [
        {
            "blocked": True,
            "stage": "company",
            "reason": "No verified official domain.",
            "company": "UnverifiedCo",
            "packet_id": result.packet_id,
            "run_id": result.run_id,
        }
    ]
    record = db.get_run_record(result.run_id)
    assert record is not None
    assert record["status"] == "failed"
    assert record["completed_at"] is not None


def test_cancelled_pipeline_closes_run_record(tmp_db, monkeypatch):
    _install_stubs(monkeypatch)
    monkeypatch.setattr(profile, "run", lambda _: time.sleep(0.1) or _stub_profile())

    async def cancel_run():
        task = asyncio.create_task(run_pipeline("AcmeCorp", "ai_infra", "profile"))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_run())

    record = db.list_run_records(limit=1)[0]
    assert record["status"] == "cancelled"
    assert record["completed_at"] is not None
    assert record["error_message"] == "Run cancelled because the client disconnected."


def test_run_pipeline_without_callback(tmp_db, monkeypatch):
    """Verify run_pipeline works without a progress callback."""
    _install_stubs(monkeypatch)
    result = asyncio.run(run_pipeline("AcmeCorp", "ai_infra", "profile"))
    assert result.status == "complete"
    assert result.run_id is not None


def test_run_pipeline_db_company_reused(tmp_db, monkeypatch):
    """If company already exists, run_pipeline updates it rather than failing."""
    _install_stubs(monkeypatch)

    r1 = asyncio.run(run_pipeline("AcmeCorp", "ai_infra", "profile"))
    r2 = asyncio.run(run_pipeline("AcmeCorp", "ai_infra", "profile"))

    assert r1.run_id != r2.run_id
    assert r2.status == "complete"
    company = db.get_company("AcmeCorp")
    assert company is not None
    assert db.get_run_record(r1.run_id) is not None
    assert db.get_run_record(r2.run_id) is not None
