from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import db
import server
from upsearch.orchestrator_service import RunResult


@pytest.fixture
def api_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "api.db")
    monkeypatch.setattr(server, "PROFILE_PATH", tmp_path / "profile.txt")
    db.init_db()
    return tmp_path


def seed_packet(company_name: str = "Acme", verification: dict | None = None) -> tuple[int, int]:
    company_id = db.upsert_company(
        company_name,
        identity_status="verified",
        identity_confidence=1,
        official_domain="acme.example",
    )
    person_id = db.insert_person(
        company_id,
        "Ada Engineer",
        "Infrastructure Engineer",
        source_url="https://acme.example/team/ada",
        verification_status="verified",
        relevance_score=8,
    )
    packet_id = db.upsert_packet(
        company_id,
        technical_note="Source-backed technical note. " * 40,
        outreach_drafts={"linkedin_note": "Hello Ada"},
        verification=verification or {"passed": True, "score": 8, "flags": []},
        qa_score=8,
        qa_flags=[],
        crm_status="prepared",
    )
    db.insert_message(packet_id, person_id, "linkedin_note", "Hello Ada")
    return company_id, packet_id


def test_historical_packet_is_explicitly_trace_unavailable(api_db):
    seed_packet("Historical Co")

    detail = server.os_get_packet("Historical Co")

    assert detail.trace_status == "unavailable"
    assert detail.run is None
    assert detail.trace == []
    assert detail.checkup is not None
    assert detail.checkup.trace_status == "unavailable"


def test_run_endpoint_returns_typed_restart_safe_state(api_db):
    seed_packet()
    run_id = db.create_run_record("Acme", "ai_infra")
    db.insert_trace_event(
        run_id,
        "agent_step",
        agent="profile",
        agent_role="Parse profile",
        reads=["profile_text"],
        writes=["user_profile"],
        output_summary="profile loaded",
        payload={"event_type": "agent_step"},
    )
    db.update_run_record(
        run_id,
        status="complete",
        current_step="qa",
        steps_completed=["profile", "qa"],
        qa_score=8,
        final_status="prepared",
    )

    state = server.os_get_run(run_id)

    assert state.run.run_id == run_id
    assert state.run.status == "complete"
    assert state.trace_status == "complete"
    assert state.trace[0].agent == "profile"
    assert state.qa is not None
    assert state.approval_state == "required"
    assert len(state.handoff_readiness) == 1


def test_packet_contract_exposes_qa_approval_and_handoff(api_db):
    seed_packet()

    detail = server.os_get_packet("Acme")

    assert detail.qa is not None
    assert detail.qa.score == 8
    assert detail.qa.model_route is None
    assert detail.approval_state == "required"
    assert detail.handoff_readiness[0].message_id > 0
    assert detail.handoff_readiness[0].approval_contract


def test_packet_qa_passes_through_degraded_model_route(api_db):
    seed_packet(
        "Degraded Co",
        verification={
            "passed": True,
            "score": 7,
            "flags": [],
            "model_route": {
                "provider": "deepseek",
                "model": "deepseek-chat",
                "configured": False,
                "is_fallback": True,
                "degraded_mode": True,
                "reason": "strong model not configured",
            },
        },
    )

    detail = server.os_get_packet("Degraded Co")

    assert detail.qa is not None
    assert detail.qa.model_route is not None
    assert detail.qa.model_route.degraded_mode is True
    assert detail.qa.model_route.is_fallback is True
    assert detail.qa.model_route.provider == "deepseek"
    assert detail.qa.model_route.reason == "strong model not configured"


def test_sse_emits_keepalive_during_long_agent_call(
    api_db,
    monkeypatch: pytest.MonkeyPatch,
):
    async def slow_pipeline(company_name, lane, profile_text, **_kwargs):
        await asyncio.sleep(0.04)
        return RunResult(
            run_id="slow-run",
            company_name=company_name,
            lane=lane,
            status="complete",
        )

    monkeypatch.setattr(server, "run_pipeline", slow_pipeline)
    monkeypatch.setattr(server, "SSE_KEEPALIVE_SECONDS", 0.01)

    with TestClient(server.app) as client:
        response = client.get("/os/packet/stream/SlowCo")

    assert response.status_code == 200
    assert "event: keepalive" in response.text
