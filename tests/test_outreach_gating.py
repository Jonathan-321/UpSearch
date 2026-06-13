"""Outreach gating: drafts must only ever target verified people.

``run_pipeline`` is exercised with fake agents and a temporary SQLite
database (same pattern as ``tests/test_orchestrator_service.py``); no
network, credentials, or real model calls are involved.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

import db
from agents import company, outreach, people, problem, profile, qa, technical_note
from upsearch.orchestrator_service import (
    OUTREACH_SKIP_NO_VERIFIED_PERSON,
    run_pipeline,
    select_top_person,
)


UNVERIFIED_HIGH = {
    "name": "Liang Xiong",
    "role": "Distinguished Engineer",
    "source_url": "https://acme.example.com/blog/scaling",
    "verification_status": "unverified",
    "relevance_score": 10,
    "relevance_reason": "Wrote the scaling blog post",
    "proximity": "engineer",
}

VERIFIED_LOWER = {
    "name": "Ada Verified",
    "role": "Infrastructure Engineer",
    "linkedin_url": "https://www.linkedin.com/in/ada-verified",
    "source_url": "https://acme.example.com/team/ada",
    "verification_status": "verified",
    "relevance_score": 8,
    "relevance_reason": "Owns inference reliability work",
    "proximity": "engineer",
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def tmp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Temporary database and tracking dir so no repo state is touched."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setenv("UPSEARCH_TRACKING_DIR", str(tmp_path / "runs"))
    db.init_db()
    return db_path


def _install_stubs(
    monkeypatch: pytest.MonkeyPatch,
    *,
    people_payload: list[dict],
    outreach_calls: list[dict],
) -> None:
    """Replace every agent entry point used by run_pipeline with fakes."""
    monkeypatch.setattr(
        profile,
        "run",
        lambda _text: {
            "name": "Test User",
            "school": "Test University",
            "background": "ML systems and evaluation",
        },
    )
    monkeypatch.setattr(
        company,
        "run",
        lambda name, _lane, _profile: {
            "result": {
                "name": name,
                "website": "https://acme.example.com",
                "official_domain": "acme.example.com",
                "identity_status": "verified",
                "identity_confidence": 0.9,
                "fit_score": 8,
                "hiring_status": "hiring",
                "what_they_do": "AI infrastructure",
                "why": "Strong public technical fit",
            },
            "source_urls": ["https://acme.example.com/about"],
        },
    )
    monkeypatch.setattr(
        problem,
        "run",
        lambda _name, _company, _profile: {
            "result": {
                "problems": [{
                    "title": "Tail latency under bursty inference load",
                    "description": "Queueing and cache pressure increase tail latency.",
                    "source_urls": [
                        "https://acme.example.com/blog/latency",
                        "https://news.ycombinator.com/item?id=1",
                    ],
                    "relevance_score": 9,
                }],
            },
            "source_urls": [
                "https://acme.example.com/blog/latency",
                "https://news.ycombinator.com/item?id=1",
            ],
        },
    )
    monkeypatch.setattr(
        people,
        "run",
        lambda _name, _problem, _profile, company_domain="": {
            "result": {"people": [dict(person) for person in people_payload]},
            "source_urls": [person.get("source_url", "") for person in people_payload],
        },
    )
    monkeypatch.setattr(
        technical_note,
        "run",
        lambda _name, _company, _problem, _profile: {
            "result": {
                "technical_note": " ".join(
                    ["Concrete queueing benchmark plan with explicit latency success criteria."] * 45
                ),
                "adjacent_proof": "https://github.com/example/inference-benchmark",
            },
        },
    )

    def _fake_outreach(_name, _problem, person, _note, _proof, _profile):
        outreach_calls.append(dict(person))
        return {
            "result": {
                "email": "Hi, short source-backed note on tail latency.",
                "linkedin_note": "Hi, I wrote a short note on burst-load latency.",
            },
        }

    monkeypatch.setattr(outreach, "run", _fake_outreach)
    monkeypatch.setattr(
        qa,
        "run",
        lambda _packet, _profile: {"score": 8, "passed": True, "flags": []},
    )


def _spy_insert_message(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Record every db.insert_message call while preserving real behavior."""
    calls: list[dict] = []
    real_insert_message = db.insert_message

    def spy(packet_id, person_id, variant, content):
        calls.append({"packet_id": packet_id, "person_id": person_id, "variant": variant})
        return real_insert_message(packet_id, person_id, variant, content)

    monkeypatch.setattr(db, "insert_message", spy)
    return calls


# ── Selection unit behavior ───────────────────────────────────────────────────


def test_select_top_person_only_ranks_verified_people():
    other_verified = {
        "name": "Cam Verified",
        "verification_status": "verified",
        "relevance_score": 9,
    }
    chosen = select_top_person([UNVERIFIED_HIGH, VERIFIED_LOWER, other_verified])
    assert chosen is not None
    assert chosen["name"] == "Cam Verified"

    assert select_top_person([UNVERIFIED_HIGH]) is None
    assert select_top_person([]) is None


# ── (a) Verified person beats higher-scoring unverified person ────────────────


def test_verified_person_selected_over_higher_scoring_unverified(tmp_db, monkeypatch):
    outreach_calls: list[dict] = []
    _install_stubs(
        monkeypatch,
        people_payload=[UNVERIFIED_HIGH, VERIFIED_LOWER],
        outreach_calls=outreach_calls,
    )
    message_calls = _spy_insert_message(monkeypatch)

    result = asyncio.run(run_pipeline("AcmeCorp", "ai_infra", "profile text"))

    assert result.status == "complete"

    # The drafting model was called exactly once, for the verified person,
    # even though the unverified person has the higher relevance score.
    assert [call["name"] for call in outreach_calls] == ["Ada Verified"]
    assert outreach_calls[0]["verification_status"] == "verified"

    stored_people = db.get_people(result.db_company_id)
    assert {person["name"] for person in stored_people} == {"Liang Xiong", "Ada Verified"}
    ada_id = next(p["id"] for p in stored_people if p["name"] == "Ada Verified")
    liang_id = next(p["id"] for p in stored_people if p["name"] == "Liang Xiong")

    # Every inserted message targets the verified person only.
    assert message_calls
    assert all(call["person_id"] == ada_id for call in message_calls)
    assert all(call["person_id"] != liang_id for call in message_calls)

    # The unverified person stays in the packet's people_map for research.
    packet = db.get_packet(result.db_company_id)
    people_map = json.loads(packet["people_map"])
    assert {person["name"] for person in people_map} == {"Liang Xiong", "Ada Verified"}


# ── (b) Zero verified people: skip outreach, insert nothing ───────────────────


def test_no_verified_person_skips_outreach_and_inserts_no_messages(tmp_db, monkeypatch):
    outreach_calls: list[dict] = []
    _install_stubs(
        monkeypatch,
        people_payload=[UNVERIFIED_HIGH],
        outreach_calls=outreach_calls,
    )
    message_calls = _spy_insert_message(monkeypatch)
    events: list[tuple[str, dict]] = []

    result = asyncio.run(
        run_pipeline(
            "AcmeCorp",
            "ai_infra",
            "profile text",
            progress_callback=lambda event, data: events.append((event, data)),
        )
    )

    # The outreach drafting model was never called and db.insert_message was
    # never reached: the inbox cannot contain drafts for unverified people.
    assert outreach_calls == []
    assert message_calls == []
    assert db.get_company_messages(result.db_company_id) == []

    # The outreach stage still completed, with zero drafts and an explicit
    # explanation in the run log.
    assert result.outreach_drafts == {}
    outreach_stages = [d for e, d in events if e == "stage" and d.get("stage") == "outreach"]
    assert outreach_stages[-1]["status"] == "complete"
    assert outreach_stages[-1]["data"] == {}
    log_messages = [d.get("message") for e, d in events if e == "log"]
    assert OUTREACH_SKIP_NO_VERIFIED_PERSON in log_messages

    # The run did not crash: QA ran and the final checkup categorized the
    # packet as weak_person_mapping (review, not outreach).
    qa_stages = [d for e, d in events if e == "stage" and d.get("stage") == "qa"]
    assert any(d.get("status") == "complete" for d in qa_stages)
    checkups = [d for e, d in events if e == "checkup"]
    assert checkups and checkups[-1]["failure_category"] == "weak_person_mapping"

    # Packet persisted for human review with empty drafts.
    packet = db.get_packet(result.db_company_id)
    assert packet is not None
    assert json.loads(packet["outreach_drafts"]) == {}
    assert packet["crm_status"] == "needs_review"
    people_map = json.loads(packet["people_map"])
    assert [person["name"] for person in people_map] == ["Liang Xiong"]

    # Terminal state is a clean review block, not an exception.
    assert result.status == "blocked"
    record = db.get_run_record(result.run_id)
    assert record is not None
    assert record["final_status"] == "needs_review"
