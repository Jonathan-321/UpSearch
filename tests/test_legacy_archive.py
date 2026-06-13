"""Task 031: archive legacy discovery junk.

Pre-fix discovery left packets stuck at crm_status='identity_blocked' and
rejected/discovered companies that never produced a packet. These tests seed a
tmp-path database with that exact shape next to live rows, then assert the
read-only report lists the junk, the archive run flips only those statuses,
archived rows drop out of list_companies()//os/companies, and a second run
changes nothing. Nothing is ever deleted.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import db
import server


@pytest.fixture
def legacy_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "legacy.db")
    monkeypatch.setattr(server, "PROFILE_PATH", tmp_path / "profile.txt")
    db.init_db()

    # Live company with a real packet: never touched by the archive.
    live_id = db.upsert_company(
        "Live Co",
        identity_status="verified",
        identity_confidence=1,
        official_domain="live.example",
        status="packet_ready",
    )
    live_packet = db.upsert_packet(
        live_id,
        open_problem={"title": "Inference scheduling", "source_urls": []},
        people_map=[{"name": "Ada Lovelace", "role": "Engineer"}],
        technical_note="A source-backed technical note.",
        crm_status="needs_review",
    )

    # Pre-fix junk packet: the identity gate blocked it before discovery
    # precision landed (the production shape behind crm_status='identity_blocked').
    blocked_id = db.upsert_company(
        "Blocked Junk Co",
        identity_status="rejected",
        identity_reason="no official domain found",
        status="identity_blocked",
    )
    blocked_packet = db.upsert_packet(
        blocked_id,
        company_fit="",
        open_problem={},
        people_map=[],
        technical_note="",
        qa_score=0,
        qa_flags=["Company identity could not be verified"],
        crm_status="identity_blocked",
    )

    # Discovered company that did produce a packet: company and packet stay.
    discovered_with_packet_id = db.upsert_company(
        "Discovered Working Co",
        identity_status="discovered",
        status="packet_ready",
    )
    discovered_packet = db.upsert_packet(
        discovered_with_packet_id,
        open_problem={"title": "Cold start latency", "source_urls": []},
        people_map=[],
        technical_note="Draft note.",
        crm_status="needs_review",
    )

    # Packet-less discovery junk: archived as companies.
    ghost_discovered_id = db.upsert_company(
        "Ghost Discovered Co", identity_status="discovered", status="sourced"
    )
    ghost_rejected_id = db.upsert_company(
        "Ghost Rejected Co", identity_status="rejected", status="sourced"
    )

    # Manually added company (default identity_status='unverified'): never swept.
    unverified_ghost_id = db.upsert_company("Manual Unverified Co", status="sourced")

    return {
        "live_id": live_id,
        "live_packet": live_packet,
        "blocked_id": blocked_id,
        "blocked_packet": blocked_packet,
        "discovered_with_packet_id": discovered_with_packet_id,
        "discovered_packet": discovered_packet,
        "ghost_discovered_id": ghost_discovered_id,
        "ghost_rejected_id": ghost_rejected_id,
        "unverified_ghost_id": unverified_ghost_id,
    }


def _company_status(company_id: int) -> str:
    with db.conn() as c:
        return c.execute(
            "SELECT status FROM companies WHERE id=?", (company_id,)
        ).fetchone()["status"]


def _packet_status(packet_id: int) -> str:
    with db.conn() as c:
        return c.execute(
            "SELECT crm_status FROM packets WHERE id=?", (packet_id,)
        ).fetchone()["crm_status"]


def _listed_ids(**kwargs) -> set[int]:
    return {company["id"] for company in db.list_companies(**kwargs)}


def test_report_counts_junk_without_mutating(legacy_db):
    ids = legacy_db
    report = db.legacy_archive_report()

    assert report["packets_total"] == 3
    assert report["packets_to_archive"] == 1
    assert report["companies_total"] == 6
    assert report["companies_to_archive"] == 2

    [packet_entry] = report["archive_packets"]
    assert packet_entry == {
        "packet_id": ids["blocked_packet"],
        "company_id": ids["blocked_id"],
        "company_name": "Blocked Junk Co",
        "identity_status": "rejected",
    }
    by_id = {entry["company_id"]: entry for entry in report["archive_companies"]}
    assert set(by_id) == {ids["ghost_discovered_id"], ids["ghost_rejected_id"]}
    assert by_id[ids["ghost_discovered_id"]]["name"] == "Ghost Discovered Co"
    assert by_id[ids["ghost_discovered_id"]]["identity_status"] == "discovered"
    assert by_id[ids["ghost_rejected_id"]]["identity_status"] == "rejected"

    # Read-only: nothing changed.
    assert _packet_status(ids["blocked_packet"]) == "identity_blocked"
    assert _company_status(ids["ghost_discovered_id"]) == "sourced"
    assert _company_status(ids["ghost_rejected_id"]) == "sourced"
    assert len(db.list_companies()) == 6


def test_run_archives_packets_and_companies(legacy_db):
    ids = legacy_db
    summary = db.run_legacy_archive()

    assert summary == {"packets_archived": 1, "companies_archived": 2}

    # The junk flipped to archived; nothing was deleted.
    assert _packet_status(ids["blocked_packet"]) == "archived"
    assert _company_status(ids["ghost_discovered_id"]) == "archived"
    assert _company_status(ids["ghost_rejected_id"]) == "archived"
    with db.conn() as c:
        assert c.execute("SELECT COUNT(*) FROM packets").fetchone()[0] == 3
        assert c.execute("SELECT COUNT(*) FROM companies").fetchone()[0] == 6

    # Live rows untouched: statuses, packets, and the manual unverified company.
    assert _company_status(ids["live_id"]) == "packet_ready"
    assert _packet_status(ids["live_packet"]) == "needs_review"
    assert _company_status(ids["discovered_with_packet_id"]) == "packet_ready"
    assert _packet_status(ids["discovered_packet"]) == "needs_review"
    assert _company_status(ids["unverified_ghost_id"]) == "sourced"
    # The blocked company keeps its own status; its archived packet hides it.
    assert _company_status(ids["blocked_id"]) == "identity_blocked"


def test_archived_rows_drop_out_of_company_listing(legacy_db):
    ids = legacy_db
    assert _listed_ids() == set(ids[key] for key in (
        "live_id", "blocked_id", "discovered_with_packet_id",
        "ghost_discovered_id", "ghost_rejected_id", "unverified_ghost_id",
    ))

    db.run_legacy_archive()

    # Default listing hides archived companies and archived-packet carriers.
    assert _listed_ids() == {
        ids["live_id"], ids["discovered_with_packet_id"], ids["unverified_ghost_id"]
    }
    # The operator can still inspect everything on request.
    assert len(db.list_companies(include_archived=True)) == 6
    assert _listed_ids(status="archived") == {
        ids["ghost_discovered_id"], ids["ghost_rejected_id"]
    }


def test_run_is_idempotent(legacy_db):
    db.run_legacy_archive()
    second = db.run_legacy_archive()
    assert second == {"packets_archived": 0, "companies_archived": 0}

    report = db.legacy_archive_report()
    assert report["packets_to_archive"] == 0
    assert report["companies_to_archive"] == 0
    assert report["archive_packets"] == []
    assert report["archive_companies"] == []


def test_maintenance_endpoints_get_reports_post_runs(legacy_db):
    ids = legacy_db
    with TestClient(server.app) as client:
        preview = client.get("/os/maintenance/legacy-archive")
        assert preview.status_code == 200
        assert preview.json()["packets_to_archive"] == 1
        assert preview.json()["companies_to_archive"] == 2

        # GET must not mutate.
        assert _packet_status(ids["blocked_packet"]) == "identity_blocked"
        assert _company_status(ids["ghost_rejected_id"]) == "sourced"

        run = client.post("/os/maintenance/legacy-archive")
        assert run.status_code == 200
        assert run.json() == {"packets_archived": 1, "companies_archived": 2}

        after = client.get("/os/maintenance/legacy-archive")
        assert after.status_code == 200
        assert after.json()["packets_to_archive"] == 0
        assert after.json()["companies_to_archive"] == 0

        # The CRM list the frontend renders no longer carries the junk.
        companies = client.get("/os/companies")
        assert companies.status_code == 200
        listed = {company["id"] for company in companies.json()["companies"]}
        assert listed == {
            ids["live_id"], ids["discovered_with_packet_id"], ids["unverified_ghost_id"]
        }
