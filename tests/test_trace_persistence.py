from __future__ import annotations

import asyncio

import pytest

import db
from upsearch.orchestrator_service import run_pipeline


@pytest.fixture
def trace_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "trace.db")
    db.init_db()
    return tmp_path


def test_trace_event_round_trip_preserves_structured_payload(trace_db):
    run_id = db.create_run_record("Acme", "ai_infra")

    db.insert_trace_event(
        run_id,
        "gate",
        status="retry",
        reason="Source coverage is weak.",
        payload={"action": "retry", "stage": "problem", "retry_count": 1},
    )

    events = db.get_trace_events(run_id)
    assert len(events) == 1
    assert events[0]["event_type"] == "gate"
    assert events[0]["status"] == "retry"
    assert events[0]["payload"]["retry_count"] == 1


def test_pipeline_persists_steps_handoffs_and_block(
    trace_db,
    monkeypatch: pytest.MonkeyPatch,
):
    import agents.company
    import agents.profile

    monkeypatch.setattr(
        agents.profile,
        "run",
        lambda _text: {"name": "Test User", "school": "Test University"},
    )
    monkeypatch.setattr(
        agents.company,
        "run",
        lambda *_args, **_kwargs: {
            "result": {
                "name": "Ambiguous Co",
                "identity_status": "unverified",
                "identity_reason": "No official domain evidence.",
                "fit_score": 5,
            },
            "source_urls": [],
        },
    )

    result = asyncio.run(
        run_pipeline("Ambiguous Co", "ai_infra", "Test profile")
    )
    events = db.get_trace_events(result.run_id)
    event_types = [event["event_type"] for event in events]

    assert result.status == "blocked"
    assert event_types.count("agent_step") == 2
    assert event_types.count("handoff") == 2
    assert "block" in event_types
    assert all(event["run_id"] == result.run_id for event in events)


def test_pipeline_persists_error_event(
    trace_db,
    monkeypatch: pytest.MonkeyPatch,
):
    import agents.profile

    def fail_profile(_text):
        raise RuntimeError("profile parser failed")

    monkeypatch.setattr(agents.profile, "run", fail_profile)

    with pytest.raises(RuntimeError, match="profile parser failed"):
        asyncio.run(run_pipeline("Acme", "ai_infra", "Test profile"))

    runs = db.list_run_records()
    assert len(runs) == 1
    events = db.get_trace_events(runs[0]["run_id"])
    assert any(
        event["event_type"] == "error"
        and event["payload"]["error"] == "profile parser failed"
        for event in events
    )


def test_historical_packet_without_run_metadata_has_no_trace(trace_db):
    company_id = db.upsert_company("Historical Co", identity_status="verified")
    db.upsert_packet(
        company_id,
        technical_note="Historical note",
        outreach_drafts={},
        verification={"passed": False},
        qa_score=0,
        qa_flags=[],
        crm_status="needs_review",
    )

    assert db.get_latest_run_record("Historical Co") is None

