from __future__ import annotations

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import db
import server


@pytest.fixture
def delivery_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "delivery.db")
    monkeypatch.setattr(server, "PROFILE_PATH", tmp_path / "profile.txt")
    monkeypatch.setattr(
        server,
        "load_checkup",
        lambda _company: {
            "failure_category": "none",
            "overall_score": 8,
            "status": "passed",
        },
    )
    monkeypatch.setattr(server, "current_profile_markers", lambda: {"name": "", "school": ""})
    db.init_db()

    company_id = db.upsert_company(
        "Delivery Co",
        identity_status="verified",
        identity_confidence=1,
        official_domain="delivery.example",
    )
    person_id = db.insert_person(
        company_id,
        "Ada Engineer",
        "Infrastructure Engineer",
        linkedin_url="https://www.linkedin.com/in/ada-engineer",
        source_url="https://delivery.example/team/ada",
        verification_status="verified",
        relevance_score=9,
    )
    packet_id = db.upsert_packet(
        company_id,
        open_problem={
            "title": "Inference scheduling",
            "source_urls": ["https://delivery.example/blog/inference"],
        },
        technical_note="A source-backed technical note. " * 40,
        verification={"passed": True, "score": 8, "flags": []},
        qa_score=8,
        qa_flags=[],
        crm_status="prepared",
    )
    message_id = db.insert_message(
        packet_id,
        person_id,
        "linkedin_note",
        "Hi Ada, I studied your team's inference scheduling work and wrote a short note.",
    )
    return message_id


def test_delivery_events_are_digest_bound_and_idempotent(delivery_db):
    message_id = delivery_db
    message = db.get_message(message_id)
    digest = db.message_digest(message["content"])
    approval_id = db.approve_message(
        message_id,
        body_digest=digest,
        channel="linkedin",
        target="https://www.linkedin.com/in/ada-engineer",
    )

    first = db.record_delivery_event(message_id, approval_id, "linkedin", status="opened")
    duplicate = db.record_delivery_event(message_id, approval_id, "linkedin", status="opened")
    assert first == duplicate

    failed = db.record_delivery_event(
        message_id,
        approval_id,
        "linkedin",
        status="failed",
        error_message="The platform did not confirm the action.",
    )
    assert failed != first
    latest = db.get_latest_delivery(message_id)
    assert latest["status"] == "failed"
    assert latest["stale"] is False
    assert db.get_approval(message_id)["id"] == approval_id
    assert db.get_message(message_id)["status"] == "approved"


def test_edited_message_cannot_inherit_delivery_or_follow_up(delivery_db):
    message_id = delivery_db
    message = db.get_message(message_id)
    approval_id = db.approve_message(
        message_id,
        body_digest=db.message_digest(message["content"]),
        channel="linkedin",
        target="https://www.linkedin.com/in/ada-engineer",
    )
    db.record_delivery_event(message_id, approval_id, "linkedin", status="sent")
    follow_up_id = db.insert_follow_up(
        message_id,
        date.today(),
        "Check for a reply.",
        approval_id=approval_id,
    )

    with db.conn() as connection:
        connection.execute(
            "UPDATE messages SET content=? WHERE id=?",
            ("Edited after approval.", message_id),
        )

    with pytest.raises(ValueError, match="stale"):
        db.record_delivery_event(message_id, approval_id, "linkedin", status="delivered")
    with pytest.raises(ValueError, match="stale"):
        db.update_follow_up(follow_up_id, "completed")

    review = next(item for item in db.get_review_messages() if item["id"] == message_id)
    assert review["approval_current"] is False
    assert review["state_stale"] is True
    assert review["delivery_status"] is None
    assert review["follow_up_status"] is None
    assert db.get_due_follow_ups() == []


def test_follow_up_is_idempotent_and_queryable(delivery_db):
    message_id = delivery_db
    message = db.get_message(message_id)
    approval_id = db.approve_message(
        message_id,
        body_digest=db.message_digest(message["content"]),
        channel="linkedin",
        target="https://www.linkedin.com/in/ada-engineer",
    )
    db.record_delivery_event(message_id, approval_id, "linkedin", status="sent")
    due = date.today() + timedelta(days=7)

    first = db.insert_follow_up(message_id, due, "Review for a response.", approval_id=approval_id)
    duplicate = db.insert_follow_up(message_id, due, "Review for a response.", approval_id=approval_id)
    assert first == duplicate

    follow_up = db.get_follow_ups_for_message(message_id)[0]
    assert follow_up["status"] == "pending"
    assert follow_up["due_date"] == due.isoformat()
    assert follow_up["stale"] is False

    db.update_follow_up(first, "completed", "Received a reply.")
    updated = db.get_follow_ups_for_message(message_id)[0]
    assert updated["status"] == "completed"
    assert updated["notes"] == "Received a reply."


def test_review_api_exposes_manual_delivery_and_follow_up_lifecycle(delivery_db):
    message_id = delivery_db

    with TestClient(server.app) as client:
        initial = client.get("/os/messages/review")
        assert initial.status_code == 200
        draft = next(item for item in initial.json() if item["id"] == message_id)
        assert draft["status"] == "draft"
        assert draft["actionable"] is True

        approved = client.post(f"/os/messages/{message_id}/approve")
        assert approved.status_code == 200
        assert approved.json()["approval_id"] > 0

        prepared = next(
            item for item in client.get("/os/messages/review").json()
            if item["id"] == message_id
        )
        assert prepared["status"] == "approved"
        assert prepared["approval_current"] is True
        assert prepared["delivery_status"] == "prepared"

        failed = client.post(
            f"/os/messages/{message_id}/delivery",
            json={"status": "unknown", "error_message": "No platform receipt was available."},
        )
        assert failed.status_code == 200
        retry_state = next(
            item for item in client.get("/os/messages/review").json()
            if item["id"] == message_id
        )
        assert retry_state["delivery_status"] == "unknown"
        assert retry_state["safe_retry"] is True

        sent = client.post(
            f"/os/messages/{message_id}/delivery",
            json={"status": "sent"},
        )
        assert sent.status_code == 200

        due = (date.today() + timedelta(days=7)).isoformat()
        follow_up = client.post(
            f"/os/messages/{message_id}/follow-ups",
            json={"due_date": due, "notes": "Review for a response."},
        )
        assert follow_up.status_code == 200
        follow_up_id = follow_up.json()["id"]

        completed = client.patch(
            f"/os/follow-ups/{follow_up_id}",
            json={"status": "completed", "notes": "Reply received."},
        )
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"


def test_api_blocks_delivery_and_follow_up_after_edit(delivery_db):
    message_id = delivery_db

    with TestClient(server.app) as client:
        assert client.post(f"/os/messages/{message_id}/approve").status_code == 200
        assert client.post(
            f"/os/messages/{message_id}/delivery",
            json={"status": "sent"},
        ).status_code == 200

        with db.conn() as connection:
            connection.execute(
                "UPDATE messages SET content=? WHERE id=?",
                ("This body no longer matches the approval.", message_id),
            )

        delivery = client.post(
            f"/os/messages/{message_id}/delivery",
            json={"status": "delivered"},
        )
        assert delivery.status_code == 409

        follow_up = client.post(
            f"/os/messages/{message_id}/follow-ups",
            json={"due_date": date.today().isoformat(), "notes": "Should be blocked."},
        )
        assert follow_up.status_code == 409

        review = next(
            item for item in client.get("/os/messages/review").json()
            if item["id"] == message_id
        )
        assert review["state_stale"] is True
        assert review["approval_current"] is False
        assert review["delivery_status"] is None

        reapproved = client.post(f"/os/messages/{message_id}/approve")
        assert reapproved.status_code == 200
        refreshed = next(
            item for item in client.get("/os/messages/review").json()
            if item["id"] == message_id
        )
        assert refreshed["approval_current"] is True
        assert refreshed["state_stale"] is False
        assert refreshed["delivery_status"] == "prepared"
        assert refreshed["follow_up_status"] is None
