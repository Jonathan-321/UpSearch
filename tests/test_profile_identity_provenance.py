"""Task 015: identity-safe profile ingestion and provenance."""

from contextlib import nullcontext
import json

import httpx

from agents import profile
from upsearch import profile_harness, profile_source_fetch
from upsearch.profile_harness import build_profile_harness_report, enrich_profile_text
from upsearch.profile_source_fetch import SourceFetchItem


def _write_cache(path, facts, sources):
    path.write_text(json.dumps({
        "fetched_at": "2026-06-11T00:00:00+00:00",
        "sources": sources,
        "proof_candidates": [],
        "warnings": [],
        "profile_facts": facts,
    }), encoding="utf-8")


def test_enrich_profile_text_makes_no_network_calls(monkeypatch) -> None:
    monkeypatch.setattr(
        profile_source_fetch,
        "load_cached_report",
        lambda: {"proof_candidates": ["GitHub proof. Source: https://github.com/student"], "warnings": []},
    )

    def _fail(*args, **kwargs):
        raise AssertionError("enrich_profile_text must not perform network calls")

    monkeypatch.setattr(httpx, "get", _fail)
    monkeypatch.setattr(httpx, "Client", _fail)

    enriched = enrich_profile_text("Name: Student\nWebsite: https://example.dev")

    assert "GitHub proof" in enriched
    assert "University course signal" not in enriched


def test_user_typed_identity_wins_and_conflict_is_visible(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "profile.json"
    _write_cache(
        cache_path,
        {"name": "Other Person", "email": "other@example.dev"},
        [{
            "kind": "web",
            "url": "https://example.dev",
            "status": "fetched",
            "discovered_from": "",
            "proof_candidates": [],
            "warnings": [],
        }],
    )
    monkeypatch.setattr(profile_harness, "PROFILE_SOURCE_CACHE_PATH", cache_path)

    report = build_profile_harness_report(
        "Name: Jonathan Muhire\nEmail: me@example.com\nWebsite: https://example.dev",
        structured_profile={"name": "Model Name", "proof_points": [], "interests": []},
    )

    assert report["profile_name"] == "Jonathan Muhire"
    assert report["email"] == "me@example.com"
    assert len(report["identity_warnings"]) == 2
    assert any("Other Person" in warning for warning in report["identity_warnings"])
    assert any("Jonathan Muhire" in warning for warning in report["identity_warnings"])


def test_fetched_identity_fills_blanks_without_warning(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "profile.json"
    _write_cache(
        cache_path,
        {"name": "Student Name", "school": "Verified University"},
        [{
            "kind": "web",
            "url": "https://example.dev",
            "status": "fetched",
            "discovered_from": "",
            "proof_candidates": [],
            "warnings": [],
        }],
    )
    monkeypatch.setattr(profile_harness, "PROFILE_SOURCE_CACHE_PATH", cache_path)

    report = build_profile_harness_report(
        "Website: https://example.dev",
        structured_profile={"name": "Model Name", "proof_points": [], "interests": []},
    )

    assert report["profile_name"] == "Student Name"
    assert report["school"] == "Verified University"
    assert report["identity_warnings"] == []


def test_fact_merge_honors_priority_and_origin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(profile_source_fetch, "CACHE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(profile_source_fetch, "_client", lambda: nullcontext(object()))
    monkeypatch.setattr(
        profile_source_fetch,
        "_fetch_web",
        lambda client, url, discovered_from="": SourceFetchItem(
            kind="web",
            url=url,
            status="fetched",
            discovered_urls=["https://github.com/student"],
            facts={"name": "Web Name", "website": "https://example.dev"},
            discovered_from=discovered_from,
        ),
    )
    monkeypatch.setattr(
        profile_source_fetch,
        "_fetch_resume",
        lambda client, url, discovered_from="": SourceFetchItem(
            kind="resume",
            url=url,
            status="fetched",
            facts={"name": "Resume Name", "email": "student@example.dev"},
            discovered_from=discovered_from,
        ),
    )
    monkeypatch.setattr(
        profile_source_fetch,
        "_fetch_github",
        lambda client, url, discovered_from="": SourceFetchItem(
            kind="github",
            url=url,
            status="fetched",
            facts={"name": "GitHub Name", "github_url": "https://github.com/student"},
            discovered_from=discovered_from,
        ),
    )

    report = profile_source_fetch.fetch_profile_sources(
        "Website: https://example.dev\nResume: https://example.dev/resume.pdf"
    )

    # Seed resume outranks seed web; the discovered GitHub profile never
    # overrides either, but still supplies facts nothing else provides.
    assert report["profile_facts"]["name"] == "Resume Name"
    assert report["profile_facts"]["email"] == "student@example.dev"
    assert report["profile_facts"]["website"] == "https://example.dev"
    assert report["profile_facts"]["github_url"] == "https://github.com/student"
    assert report["fact_provenance"]["name"] == "https://example.dev/resume.pdf"
    assert report["fact_provenance"]["github_url"] == "https://github.com/student"


def test_proof_provenance_marks_user_seed_and_discovered_claims(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "profile.json"
    _write_cache(
        cache_path,
        {},
        [
            {
                "kind": "web",
                "url": "https://example.dev",
                "status": "fetched",
                "discovered_from": "",
                "proof_candidates": ["Website proof. Source: https://example.dev"],
                "warnings": [],
            },
            {
                "kind": "resume",
                "url": "https://example.dev/resume.pdf",
                "status": "fetched",
                "discovered_from": "https://example.dev",
                "proof_candidates": ["Resume proof. Source: https://example.dev/resume.pdf"],
                "warnings": [],
            },
        ],
    )
    monkeypatch.setattr(profile_harness, "PROFILE_SOURCE_CACHE_PATH", cache_path)

    report = build_profile_harness_report(
        "Website: https://example.dev",
        structured_profile={
            "name": "Student Name",
            "proof_points": ["Built a course project in class"],
            "interests": [],
        },
    )

    provenance = {item["claim"]: item for item in report["proof_provenance"]}
    assert set(provenance) == set(report["proof_bank"])
    user_claim = provenance["Built a course project in class"]
    assert user_claim["origin"] == "user"
    assert user_claim["source_url"] == ""
    web_claim = provenance["Website proof. Source: https://example.dev"]
    assert web_claim["origin"] == "seed"
    assert web_claim["source_url"] == "https://example.dev"
    assert web_claim["fetched_at"] == "2026-06-11T00:00:00+00:00"
    resume_claim = provenance["Resume proof. Source: https://example.dev/resume.pdf"]
    assert resume_claim["origin"] == "discovered"
    assert resume_claim["source_kind"] == "resume"

    origins = {source["value"]: source["origin"] for source in report["sources"]}
    assert origins["https://example.dev"] == "seed"
    assert origins["https://example.dev/resume.pdf"] == "discovered"


def test_fallback_profile_user_identity_wins(monkeypatch) -> None:
    monkeypatch.setattr(
        profile_source_fetch,
        "load_cached_report",
        lambda: {
            "profile_facts": {"name": "Other Person", "school": "Source University"},
            "proof_candidates": [],
            "sources": [],
        },
    )

    result = profile.fallback_profile("Name: Real User\nWebsite: https://example.dev")

    assert result["name"] == "Real User"
    assert result["school"] == "Source University"
