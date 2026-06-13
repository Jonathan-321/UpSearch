from pathlib import Path

import db


def test_source_store_persists_verified_claim_metadata(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    company_id = db.upsert_company(
        "AcmeFlow",
        canonical_name="AcmeFlow",
        website="https://acmeflow.ai",
        official_domain="acmeflow.ai",
        identity_status="verified",
        identity_confidence=0.9,
    )

    source_id = db.insert_source(
        "https://acmeflow.ai/blog/inference",
        title="Inference at AcmeFlow",
        source_type="company_blog",
        claim_type="open_problem",
        verified=True,
        metadata={"retriever": "company_blog"},
        company_id=company_id,
    )

    sources = db.get_sources(company_id)
    assert sources[0]["id"] == source_id
    assert sources[0]["verified"] == 1
    assert sources[0]["claim_type"] == "open_problem"


def test_entity_helpers_auto_record_sources(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()

    company_id = db.upsert_company(
        "AcmeFlow",
        website="https://acmeflow.ai",
        identity_status="verified",
        source_urls=["https://acmeflow.ai/blog/inference#section"],
    )
    problem_id = db.insert_problem(
        company_id,
        "Serving latency",
        "Public blog names latency as a production issue.",
        ["https://acmeflow.ai/blog/inference/"],
        relevance_score=8,
    )
    person_id = db.insert_person(
        company_id,
        "Taylor Kim",
        "Inference Engineer",
        source_url="https://acmeflow.ai/team/taylor",
        verification_status="verified",
    )

    sources = db.get_sources(company_id)
    assert company_id > 0
    assert problem_id > 0
    assert person_id > 0
    assert sorted(source["claim_type"] for source in sources) == [
        "company_identity",
        "open_problem",
        "person_identity",
    ]
    assert {source["url"] for source in sources} == {
        "https://acmeflow.ai/blog/inference",
        "https://acmeflow.ai/team/taylor",
    }


def test_contact_source_is_verified_only_with_exact_url_check(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    company_id = db.upsert_company("AcmeFlow", identity_status="verified")

    db.insert_person(
        company_id,
        "Taylor Kim",
        "Inference Engineer",
        source_url="https://acmeflow.ai/team/taylor",
        linkedin_url="https://linkedin.com/in/taylor-kim",
        github_url="https://github.com/taylor-kim",
        verification_status="verified",
        contact_url_checks={
            "linkedin_url": {
                "url": "https://linkedin.com/in/different-person",
                "fetched": True,
                "matched": True,
            },
            "github_url": {
                "url": "https://github.com/taylor-kim",
                "fetched": True,
                "matched": True,
            },
        },
    )

    sources = {source["url"]: source for source in db.get_sources(company_id)}
    assert sources["https://acmeflow.ai/team/taylor"]["verified"] == 1
    assert sources["https://linkedin.com/in/taylor-kim"]["verified"] == 0
    assert sources["https://github.com/taylor-kim"]["verified"] == 1


def test_packet_prepared_status_is_downgraded_when_evidence_missing(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    company_id = db.upsert_company("ThinSignal", identity_status="unverified")

    packet_id = db.upsert_packet(
        company_id,
        company_fit="Looks relevant",
        open_problem="{}",
        technical_note="note",
        outreach_drafts={"email": "hello"},
        verification={"passed": True, "score": 8, "flags": []},
        qa_score=8,
        qa_flags=[],
        crm_status="prepared",
    )

    packet = db.get_packet(company_id)
    assert packet["id"] == packet_id
    assert packet["crm_status"] == "needs_review"
    assert "Evidence gate blocked send-ready status" in packet["qa_flags"]
    assert "verified company identity" in packet["qa_flags"]


def test_packet_prepared_status_survives_when_verified_evidence_exists(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    company_id = db.upsert_company(
        "AcmeFlow",
        identity_status="verified",
        source_urls=["https://acmeflow.ai"],
    )
    problem_id = db.insert_problem(
        company_id,
        "Serving latency",
        "Public blog names latency as a production issue.",
        ["https://acmeflow.ai/blog/inference"],
        relevance_score=8,
    )
    person_id = db.insert_person(
        company_id,
        "Taylor Kim",
        "Inference Engineer",
        source_url="https://acmeflow.ai/team/taylor",
        verification_status="verified",
    )
    db.insert_source(
        "https://acmeflow.ai/blog/inference",
        claim_type="open_problem",
        source_type="company_blog",
        verified=True,
        company_id=company_id,
        problem_id=problem_id,
    )
    db.insert_source(
        "https://acmeflow.ai/team/taylor",
        claim_type="person_identity",
        source_type="company_team",
        verified=True,
        company_id=company_id,
        person_id=person_id,
    )

    db.upsert_packet(
        company_id,
        company_fit="Looks relevant",
        open_problem="{}",
        technical_note="note",
        outreach_drafts={"email": "hello"},
        verification={"passed": True, "score": 8, "flags": []},
        qa_score=8,
        qa_flags=[],
        crm_status="prepared",
    )

    packet = db.get_packet(company_id)
    assert packet["crm_status"] == "prepared"
