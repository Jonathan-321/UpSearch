from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pytest

import db
from agents import company, outreach, people, problem, profile, qa, technical_note
from upsearch.acceptance import run_golden_acceptance
from upsearch.orchestrator_service import run_pipeline
from upsearch.runtime import check_migration_state


def _install_fake_agents(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        profile,
        "run",
        lambda _text: {
            "name": "Release User",
            "school": "Release University",
            "background": "ML systems and evaluation",
        },
    )
    monkeypatch.setattr(
        company,
        "run",
        lambda name, _lane, _profile: {
            "result": {
                "name": name,
                "website": "https://release.example",
                "official_domain": "release.example",
                "identity_status": "verified",
                "identity_confidence": 1,
                "fit_score": 9,
                "hiring_status": "hiring",
                "what_they_do": "Inference infrastructure",
                "why": "Strong public technical fit",
            },
            "source_urls": ["https://release.example/about"],
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
                    "source_urls": ["https://release.example/blog/latency"],
                    "relevance_score": 9,
                }],
            },
            "source_urls": ["https://release.example/blog/latency"],
        },
    )
    monkeypatch.setattr(
        people,
        "run",
        lambda _name, _problems, _profile, company_domain="": {
            "result": {
                "people": [{
                    "name": "Ada Engineer",
                    "role": "Infrastructure Engineer",
                    "linkedin_url": "https://www.linkedin.com/in/ada-release",
                    "source_url": "https://release.example/team/ada",
                    "verification_status": "verified",
                    "relevance_score": 9,
                    "relevance_reason": "Owns inference reliability work",
                    "proximity": "engineer",
                }],
            },
            "source_urls": ["https://release.example/team/ada"],
        },
    )
    monkeypatch.setattr(
        technical_note,
        "run",
        lambda _name, _company, _problems, _profile: {
            "result": {
                "technical_note": " ".join([
                    "Build a source-backed queueing benchmark with explicit latency percentiles,"
                    " burst profiles, cache-state controls, and success criteria."
                ] * 45),
                "adjacent_proof": "https://github.com/example/inference-benchmark",
            },
        },
    )
    monkeypatch.setattr(
        outreach,
        "run",
        lambda _name, _problems, _people, _note, _proof, _profile: {
            "result": {
                "email": "Hi Ada, I studied your inference reliability work and wrote a short benchmark note.",
                "linkedin_note": "Hi Ada, I wrote a short note on burst-load inference reliability.",
            },
        },
    )
    monkeypatch.setattr(
        qa,
        "run",
        lambda _packet, _profile: {"score": 8, "passed": True, "flags": []},
    )


def test_release_integration_is_restart_and_approval_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / "state"
    db_path = state_dir / "opportunity_os.db"
    tracking_dir = state_dir / "runs"
    assert not state_dir.exists()

    state_dir.mkdir()
    monkeypatch.setattr(db, "DB_PATH", db_path)
    monkeypatch.setenv("UPSEARCH_DIR", str(state_dir))
    monkeypatch.setenv("UPSEARCH_DB_PATH", str(db_path))
    monkeypatch.setenv("UPSEARCH_TRACKING_DIR", str(tracking_dir))
    db.init_db()

    migration = check_migration_state(db_path)
    assert migration.pending_migrations == []
    assert {"run_records", "trace_events", "send_events", "follow_ups"} <= set(
        migration.tables_found
    )

    golden = run_golden_acceptance()
    assert {"Baseten", "Modal"} <= set(golden)
    assert all(result.all_passed for result in golden.values())

    _install_fake_agents(monkeypatch)
    events: list[tuple[str, dict]] = []
    run_id = "release-acceptance-run"
    result = asyncio.run(
        run_pipeline(
            "Release Co",
            "ai_infra",
            "Name: Release User\nSchool: Release University",
            run_id=run_id,
            progress_callback=lambda event, payload: events.append((event, payload)),
        )
    )

    record = db.get_run_record(run_id)
    trace = db.get_trace_events(run_id)
    packet = db.get_packet(result.db_company_id)
    assert result.run_id == run_id
    assert record["run_id"] == run_id
    assert record["qa_score"] == result.qa_result["score"]
    assert packet["id"] == result.packet_id
    assert trace and all(event["run_id"] == run_id for event in trace)
    assert events and all(payload["run_id"] == run_id for _, payload in events)

    messages = db.get_company_messages(result.db_company_id)
    message = next(item for item in messages if item["variant"] == "linkedin_note")
    with pytest.raises(ValueError, match="approval"):
        db.record_delivery_event(
            message["id"],
            999999,
            "linkedin",
            status="opened",
        )

    approval_id = db.approve_message(
        message["id"],
        channel="linkedin",
        target="https://www.linkedin.com/in/ada-release",
    )
    prepared_id = db.record_delivery_event(
        message["id"],
        approval_id,
        "linkedin",
        status="prepared",
    )
    sent_id = db.record_delivery_event(
        message["id"],
        approval_id,
        "linkedin",
        status="sent",
    )
    follow_up_id = db.insert_follow_up(
        message["id"],
        date.today() + timedelta(days=7),
        "Review for a response.",
        approval_id=approval_id,
    )

    counts_before = {}
    with db.conn() as connection:
        for table in ("packets", "approvals", "trace_events", "send_events", "follow_ups"):
            counts_before[table] = connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0]

    db.init_db()
    assert db.get_run_record(run_id)["status"] == "complete"
    assert db.approve_message(
        message["id"],
        channel="linkedin",
        target="https://www.linkedin.com/in/ada-release",
    ) == approval_id
    assert db.record_delivery_event(
        message["id"],
        approval_id,
        "linkedin",
        status="prepared",
    ) == prepared_id
    assert db.record_delivery_event(
        message["id"],
        approval_id,
        "linkedin",
        status="sent",
    ) == sent_id
    assert db.insert_follow_up(
        message["id"],
        date.today() + timedelta(days=7),
        "Review for a response.",
        approval_id=approval_id,
    ) == follow_up_id

    with db.conn() as connection:
        counts_after = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in counts_before
        }
    assert counts_after == counts_before
