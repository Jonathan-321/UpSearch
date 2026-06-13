"""Task 024: purge stored non-person junk (people rows, pending messages, people_map).
Task 027 extends the same pass with duplicate-person collapse and the stored
verification_reason column.

Seeds a tmp-path database with the junk shapes observed in production
(nav labels, group labels, duplicate rows for the same human) next to real
people, then asserts the hygiene pass removes exactly the junk, rejects only
the affected live messages, rewrites packet people maps, and is idempotent.
"""
from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import db
import server


@pytest.fixture
def hygiene_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "hygiene.db")
    monkeypatch.setattr(server, "PROFILE_PATH", tmp_path / "profile.txt")
    db.init_db()

    company_id = db.upsert_company(
        "Hygiene Co",
        identity_status="verified",
        identity_confidence=1,
        official_domain="hygiene.example",
    )
    ada_id = db.insert_person(
        company_id,
        "Ada Lovelace",
        "Infrastructure Engineer",
        source_url="https://hygiene.example/team/ada",
        linkedin_url="https://www.linkedin.com/in/ada-lovelace",
        verification_status="verified",
        relevance_score=9,
    )
    grace_id = db.insert_person(
        company_id,
        "Grace Hopper",
        "Compiler Engineer",
        source_url="https://hygiene.example/team/grace",
        relevance_score=8,
    )  # real name, verification_status stays 'unverified'
    pricing_id = db.insert_person(
        company_id,
        "Pricing",
        "Unknown",
        relevance_score=7,
    )
    use_cases_id = db.insert_person(
        company_id,
        "Use Cases",
        "Unknown",
        relevance_score=6,
    )
    contributors_id = db.insert_person(
        company_id,
        "Fireworks GitHub Contributors",
        "Engineering",
        source_url="https://hygiene.example/blog/contributors",
        relevance_score=5,
    )

    packet_id = db.upsert_packet(
        company_id,
        open_problem={"title": "Inference scheduling", "source_urls": []},
        people_map=[
            {"name": "Ada Lovelace", "role": "Infrastructure Engineer"},
            {"name": "Grace Hopper", "role": "Compiler Engineer"},
            {"name": "Pricing", "role": "Unknown"},
            {"name": "Use Cases", "role": "Unknown"},
            {"name": "Fireworks GitHub Contributors", "role": "Engineering"},
            {"name": "Platform Overview", "role": "Unknown"},  # map-only junk, no people row
        ],
        technical_note="A source-backed technical note.",
        crm_status="prepared",
    )

    m_ada = db.insert_message(packet_id, ada_id, "linkedin_note", "Hi Ada, about scheduling.")
    m_grace = db.insert_message(packet_id, grace_id, "linkedin_note", "Hi Grace, about compilers.")
    m_pricing = db.insert_message(packet_id, pricing_id, "email", "Hi Pricing team page.")
    m_use_cases = db.insert_message(packet_id, use_cases_id, "email", "Hi Use Cases nav entry.")
    db.approve_message(m_use_cases, notes="Approved before the gate existed")
    m_no_recipient = db.insert_message(packet_id, None, "email", "Packet-level draft, no recipient.")
    m_dangling = db.insert_message(packet_id, 99999, "email", "Recipient row no longer exists.")
    m_prerejected = db.insert_message(packet_id, contributors_id, "email", "Already rejected.")
    db.reject_message(m_prerejected, "Rejected by user")

    return {
        "company_id": company_id,
        "packet_id": packet_id,
        "ada_id": ada_id,
        "grace_id": grace_id,
        "pricing_id": pricing_id,
        "use_cases_id": use_cases_id,
        "contributors_id": contributors_id,
        "m_ada": m_ada,
        "m_grace": m_grace,
        "m_pricing": m_pricing,
        "m_use_cases": m_use_cases,
        "m_no_recipient": m_no_recipient,
        "m_dangling": m_dangling,
        "m_prerejected": m_prerejected,
    }


def _people_names(company_id: int) -> set[str]:
    return {person["name"] for person in db.get_people(company_id)}


def _message_status(message_id: int) -> str:
    return db.get_message(message_id)["status"]


def test_report_counts_junk_without_mutating(hygiene_db):
    ids = hygiene_db
    report = db.people_hygiene_report()

    assert report["people_total"] == 5
    assert report["people_failing"] == 3
    assert report["people_kept"] == 2
    assert report["duplicates_removed"] == 0
    assert report["duplicate_people"] == []
    # m_grace (unverified), m_pricing (junk), m_use_cases (approved, junk),
    # m_dangling (missing person row). Not m_ada, m_no_recipient, m_prerejected.
    assert report["messages_flagged"] == 4
    reasons = {entry["name"]: entry["reason"] for entry in report["failing_people"]}
    assert reasons == {
        "Pricing": "single_token",
        "Use Cases": "nav_vocabulary:use",
        "Fireworks GitHub Contributors": "nav_vocabulary:github",
    }
    flagged_ids = {entry["message_id"] for entry in report["flagged_messages"]}
    assert flagged_ids == {ids["m_grace"], ids["m_pricing"], ids["m_use_cases"], ids["m_dangling"]}

    # Read-only: nothing changed.
    assert len(_people_names(ids["company_id"])) == 5
    assert _message_status(ids["m_grace"]) == "draft"
    assert _message_status(ids["m_pricing"]) == "draft"
    assert _message_status(ids["m_use_cases"]) == "approved"


def test_run_purges_junk_people_and_rejects_their_messages(hygiene_db):
    ids = hygiene_db
    summary = db.run_people_hygiene()

    assert summary == {
        "people_removed": 3,
        "duplicates_removed": 0,
        "messages_rejected": 4,
        "packets_updated": 1,
        "people_kept": 2,
    }

    # Junk people deleted, real people intact (even when unverified).
    assert _people_names(ids["company_id"]) == {"Ada Lovelace", "Grace Hopper"}

    # Affected live messages rejected with the validation reason recorded.
    assert _message_status(ids["m_pricing"]) == "rejected"
    assert db.get_approval(ids["m_pricing"])["notes"] == (
        "recipient failed person validation: single_token"
    )
    assert _message_status(ids["m_use_cases"]) == "rejected"
    assert db.get_approval(ids["m_use_cases"])["notes"] == (
        "recipient failed person validation: nav_vocabulary:use"
    )
    assert _message_status(ids["m_grace"]) == "rejected"
    assert db.get_approval(ids["m_grace"])["notes"] == (
        "recipient failed person validation: verification_status=unverified"
    )
    assert _message_status(ids["m_dangling"]) == "rejected"
    assert db.get_approval(ids["m_dangling"])["notes"] == (
        "recipient failed person validation: person record missing"
    )

    # Untouched: verified recipient, recipient-less draft, already-terminal message.
    assert _message_status(ids["m_ada"]) == "draft"
    assert db.get_approval(ids["m_ada"]) is None
    assert _message_status(ids["m_no_recipient"]) == "draft"
    assert _message_status(ids["m_prerejected"]) == "rejected"
    assert db.get_approval(ids["m_prerejected"])["notes"] == "Rejected by user"

    # Packet people_map rewritten to drop junk, including map-only junk.
    packet = db.get_packet(ids["company_id"])
    people_map = json.loads(packet["people_map"])
    assert [entry["name"] for entry in people_map] == ["Ada Lovelace", "Grace Hopper"]

    # Junk-person evidence rows purged; real-person evidence kept.
    with db.conn() as c:
        junk_sources = c.execute(
            "SELECT COUNT(*) FROM sources WHERE person_id IN (?,?,?)",
            (ids["pricing_id"], ids["use_cases_id"], ids["contributors_id"]),
        ).fetchone()[0]
        ada_sources = c.execute(
            "SELECT COUNT(*) FROM sources WHERE person_id=?", (ids["ada_id"],)
        ).fetchone()[0]
    assert junk_sources == 0
    assert ada_sources > 0


def test_run_is_idempotent(hygiene_db):
    db.run_people_hygiene()
    second = db.run_people_hygiene()
    assert second == {
        "people_removed": 0,
        "duplicates_removed": 0,
        "messages_rejected": 0,
        "packets_updated": 0,
        "people_kept": 2,
    }
    report = db.people_hygiene_report()
    assert report["people_failing"] == 0
    assert report["messages_flagged"] == 0


def test_maintenance_endpoints_get_reports_post_runs(hygiene_db):
    ids = hygiene_db
    with TestClient(server.app) as client:
        preview = client.get("/os/maintenance/people-hygiene")
        assert preview.status_code == 200
        assert preview.json()["people_failing"] == 3
        assert preview.json()["messages_flagged"] == 4

        # GET must not mutate.
        assert len(_people_names(ids["company_id"])) == 5
        assert _message_status(ids["m_pricing"]) == "draft"

        run = client.post("/os/maintenance/people-hygiene")
        assert run.status_code == 200
        assert run.json() == {
            "people_removed": 3,
            "duplicates_removed": 0,
            "messages_rejected": 4,
            "packets_updated": 1,
            "people_kept": 2,
        }

        after = client.get("/os/maintenance/people-hygiene")
        assert after.status_code == 200
        assert after.json()["people_failing"] == 0
        assert after.json()["messages_flagged"] == 0
        assert after.json()["people_kept"] == 2


# ── Task 027: duplicate people collapse ──────────────────────────────────────


@pytest.fixture
def duplicate_db(monkeypatch: pytest.MonkeyPatch, tmp_path):
    """The production shape: the same human stored twice for one company."""
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "dupes.db")
    monkeypatch.setattr(server, "PROFILE_PATH", tmp_path / "profile.txt")
    db.init_db()

    modal_id = db.upsert_company(
        "Modal",
        identity_status="verified",
        identity_confidence=1,
        official_domain="modal.com",
    )
    erik_verified = db.insert_person(
        modal_id,
        "Erik Bernhardsson",
        "CEO",
        source_url="https://modal.com/company",
        linkedin_url="https://www.linkedin.com/in/erikbern",
        verification_status="verified",
        verification_reason="evidence_contract_passed",
        relevance_score=9,
    )
    erik_dup = db.insert_person(
        modal_id,
        "Erik BernHardsson",  # case variant of the same human
        "Founder",
        source_url="https://modal.com/blog/founders",
        github_url="https://github.com/erikbern",
        relevance_score=7,
    )
    # Both unverified: highest relevance_score wins even with a higher id.
    akshat_low = db.insert_person(modal_id, "Akshat Bubna", "Engineer", relevance_score=5)
    akshat_high = db.insert_person(modal_id, "Akshat Bubna", "Staff Engineer", relevance_score=8)
    # Full tie: lowest id wins.
    jane_first = db.insert_person(modal_id, "Jane Doe", "Engineer", relevance_score=4)
    jane_second = db.insert_person(modal_id, "Jane Doe", "Engineer", relevance_score=4)
    # Same name at another company is a different person, never deduped.
    other_id = db.upsert_company(
        "Other Co", identity_status="verified", identity_confidence=1
    )
    erik_elsewhere = db.insert_person(other_id, "Erik Bernhardsson", "Advisor", relevance_score=3)

    packet_id = db.upsert_packet(
        modal_id,
        open_problem={"title": "Cold start latency", "source_urls": []},
        people_map=[{"name": "Erik Bernhardsson", "role": "CEO"}],
        technical_note="A source-backed technical note.",
        crm_status="prepared",
    )
    m_to_dup_draft = db.insert_message(packet_id, erik_dup, "email", "Hi Erik, about cold starts.")
    m_to_dup_rejected = db.insert_message(packet_id, erik_dup, "email", "Old draft to the duplicate.")
    db.reject_message(m_to_dup_rejected, "Rejected by user")
    m_to_akshat_low = db.insert_message(packet_id, akshat_low, "email", "Hi Akshat.")

    return {
        "modal_id": modal_id,
        "other_id": other_id,
        "erik_verified": erik_verified,
        "erik_dup": erik_dup,
        "akshat_low": akshat_low,
        "akshat_high": akshat_high,
        "jane_first": jane_first,
        "jane_second": jane_second,
        "erik_elsewhere": erik_elsewhere,
        "m_to_dup_draft": m_to_dup_draft,
        "m_to_dup_rejected": m_to_dup_rejected,
        "m_to_akshat_low": m_to_akshat_low,
    }


def test_report_lists_duplicates_without_mutating(duplicate_db):
    ids = duplicate_db
    report = db.people_hygiene_report()

    assert report["people_total"] == 7
    assert report["people_failing"] == 0
    assert report["duplicates_removed"] == 3
    assert report["people_kept"] == 4
    by_kept = {entry["kept_id"]: entry for entry in report["duplicate_people"]}
    assert by_kept[ids["erik_verified"]]["removed_ids"] == [ids["erik_dup"]]
    assert by_kept[ids["akshat_high"]]["removed_ids"] == [ids["akshat_low"]]
    assert by_kept[ids["jane_first"]]["removed_ids"] == [ids["jane_second"]]
    # Same name at a different company is never part of a duplicate group.
    removed_everywhere = {rid for e in report["duplicate_people"] for rid in e["removed_ids"]}
    assert ids["erik_elsewhere"] not in removed_everywhere
    # The draft to Erik's duplicate resolves to the kept verified row, so it
    # is not flagged; the draft to Akshat resolves to an unverified row.
    assert {entry["message_id"] for entry in report["flagged_messages"]} == {
        ids["m_to_akshat_low"]
    }

    # Read-only: nothing changed.
    assert len(db.get_people(ids["modal_id"])) == 6
    assert _message_status(ids["m_to_dup_draft"]) == "draft"


def test_run_collapses_duplicates_and_repoints_messages(duplicate_db):
    ids = duplicate_db
    summary = db.run_people_hygiene()

    assert summary == {
        "people_removed": 0,
        "duplicates_removed": 3,
        "messages_rejected": 1,
        "packets_updated": 0,
        "people_kept": 4,
    }

    kept_ids = {person["id"] for person in db.get_people(ids["modal_id"])}
    assert kept_ids == {ids["erik_verified"], ids["akshat_high"], ids["jane_first"]}
    # The same-name person at the other company is untouched.
    assert {p["id"] for p in db.get_people(ids["other_id"])} == {ids["erik_elsewhere"]}

    # Messages to the removed duplicate now reference the kept row.
    draft = db.get_message(ids["m_to_dup_draft"])
    assert draft["person_id"] == ids["erik_verified"]
    assert draft["status"] == "draft"  # final recipient is verified — kept alive
    rejected = db.get_message(ids["m_to_dup_rejected"])
    assert rejected["person_id"] == ids["erik_verified"]
    assert rejected["status"] == "rejected"
    # The draft to the unverified survivor is rejected with the honest reason.
    akshat_msg = db.get_message(ids["m_to_akshat_low"])
    assert akshat_msg["person_id"] == ids["akshat_high"]
    assert akshat_msg["status"] == "rejected"
    assert db.get_approval(ids["m_to_akshat_low"])["notes"] == (
        "recipient failed person validation: verification_status=unverified"
    )

    # No evidence rows reference the deleted duplicate; its distinct URLs
    # moved to the kept row.
    with db.conn() as c:
        dangling = c.execute(
            "SELECT COUNT(*) FROM sources WHERE person_id=?", (ids["erik_dup"],)
        ).fetchone()[0]
        kept_urls = {
            row["url"]
            for row in c.execute(
                "SELECT url FROM sources WHERE person_id=?", (ids["erik_verified"],)
            ).fetchall()
        }
    assert dangling == 0
    assert "https://modal.com/blog/founders" in kept_urls
    assert "https://github.com/erikbern" in kept_urls


def test_duplicate_collapse_is_idempotent(duplicate_db):
    db.run_people_hygiene()
    second = db.run_people_hygiene()
    assert second == {
        "people_removed": 0,
        "duplicates_removed": 0,
        "messages_rejected": 0,
        "packets_updated": 0,
        "people_kept": 4,
    }
    report = db.people_hygiene_report()
    assert report["duplicates_removed"] == 0
    assert report["duplicate_people"] == []


# ── Task 027: stored verification_reason ─────────────────────────────────────


def test_insert_person_persists_verification_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "reason.db")
    db.init_db()
    company_id = db.upsert_company("Reason Co")
    with_reason = db.insert_person(
        company_id,
        "Ada Lovelace",
        "Engineer",
        verification_status="verified",
        verification_reason="evidence_contract_passed",
    )
    without_reason = db.insert_person(company_id, "Grace Hopper", "Engineer")

    rows = {person["id"]: person for person in db.get_people(company_id)}
    assert rows[with_reason]["verification_reason"] == "evidence_contract_passed"
    assert rows[without_reason]["verification_reason"] == ""


def test_init_db_adds_verification_reason_to_legacy_people_table(monkeypatch, tmp_path):
    legacy = tmp_path / "legacy.db"
    monkeypatch.setattr(db, "DB_PATH", legacy)
    raw = sqlite3.connect(legacy)
    raw.execute(
        """CREATE TABLE people (
            id INTEGER PRIMARY KEY,
            company_id INTEGER,
            name TEXT NOT NULL,
            role TEXT,
            linkedin_url TEXT,
            twitter_url TEXT,
            github_url TEXT,
            source_url TEXT,
            verification_status TEXT DEFAULT 'unverified',
            relevance_score REAL DEFAULT 0,
            relevance_reason TEXT,
            proximity TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    raw.execute(
        "INSERT INTO people (company_id, name, role) VALUES (1, 'Ada Lovelace', 'Engineer')"
    )
    raw.commit()
    raw.close()

    db.init_db()

    with db.conn() as c:
        cols = {row["name"] for row in c.execute("PRAGMA table_info(people)").fetchall()}
        row = c.execute(
            "SELECT verification_reason FROM people WHERE name='Ada Lovelace'"
        ).fetchone()
    assert "verification_reason" in cols
    assert row["verification_reason"] == ""


def test_checkup_identity_block_owns_the_diagnosis():
    """Empty problems/people on an identity-blocked packet are symptoms; the
    checkup must report identity_blocked, not empty_problem_set."""
    from upsearch.packet_checkup import decide_action, run_packet_checkup

    checkup = run_packet_checkup(
        "Oblivious GPU Cloud",
        {
            "crm_status": "identity_blocked",
            "qa_score": 0,
            "qa_flags": "[]",
            "outreach_drafts": "{}",
            "technical_note": "",
        },
        [],
        [],
        [],
    )

    assert checkup["failure_category"] == "identity_blocked"
    assert "identity" in checkup["suggested_fix"].lower()
    decision = decide_action(checkup, {})
    assert decision["action"] == "block"
    assert "identity" in decision["reason"].lower()
