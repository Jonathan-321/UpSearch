from contextlib import nullcontext
import json

from upsearch import profile_harness, profile_source_fetch
from upsearch.profile_harness import build_profile_harness_report, extract_profile_urls
from upsearch.profile_source_fetch import SourceFetchItem


def test_profile_url_extraction_does_not_treat_email_domain_as_website() -> None:
    urls = extract_profile_urls(
        "Email: student@gmail.com\nWebsite: example.dev\nGitHub: github.com/student"
    )

    assert "https://gmail.com" not in urls
    assert urls == ["https://example.dev", "https://github.com/student"]


def test_web_edges_keep_only_high_value_profile_sources() -> None:
    html = """
    <a href="/about">About</a>
    <a href="/blog/post">Blog post</a>
    <a href="/resume.pdf">Resume</a>
    <a href="https://github.com/Student/project">GitHub</a>
    <a href="https://www.linkedin.com/in/student/">LinkedIn</a>
    <a href="mailto:student@example.dev">Email</a>
    """

    urls, contacts = profile_source_fetch._extract_web_edges(html, "https://example.dev")

    assert urls == [
        "https://example.dev/about",
        "https://example.dev/resume.pdf",
        "https://github.com/Student",
        "https://www.linkedin.com/in/student",
    ]
    assert contacts == ["student@example.dev"]


def test_single_website_seed_expands_into_profile_source_graph(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(profile_source_fetch, "CACHE_PATH", tmp_path / "profile.json")
    monkeypatch.setattr(profile_source_fetch, "_client", lambda: nullcontext(object()))

    def fetch_web(client, url, discovered_from=""):
        if url == "https://example.dev":
            return SourceFetchItem(
                kind="web",
                url=url,
                status="fetched",
                proof_candidates=[f"Website proof. Source: {url}"],
                discovered_urls=[
                    "https://github.com/student/project",
                    "https://www.linkedin.com/in/student/",
                    "https://example.dev/resume.pdf",
                ],
                contact_candidates=["student@example.dev"],
                discovered_from=discovered_from,
            )
        return SourceFetchItem(kind="web", url=url, status="fetched", discovered_from=discovered_from)

    monkeypatch.setattr(profile_source_fetch, "_fetch_web", fetch_web)
    monkeypatch.setattr(
        profile_source_fetch,
        "_fetch_github",
        lambda client, url, discovered_from="": SourceFetchItem(
            kind="github",
            url=url,
            status="fetched",
            proof_candidates=[f"GitHub proof. Source: {url}"],
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
            proof_candidates=[f"Resume proof. Source: {url}"],
            discovered_from=discovered_from,
        ),
    )

    report = profile_source_fetch.fetch_profile_sources("Website: https://example.dev")

    assert report["seed_urls"] == ["https://example.dev"]
    assert [source["kind"] for source in report["sources"]] == [
        "web",
        "github",
        "linkedin",
        "resume",
    ]
    assert report["sources"][1]["url"] == "https://github.com/student"
    assert report["sources"][1]["discovered_from"] == "https://example.dev"
    assert report["sources"][2]["status"] == "auth_required"
    assert report["contact_candidates"] == ["student@example.dev"]
    assert len(report["proof_candidates"]) == 3


def test_harness_uses_discovered_resume_and_inferred_identity(tmp_path, monkeypatch) -> None:
    cache_path = tmp_path / "profile.json"
    cache_path.write_text(json.dumps({
        "fetched_at": "2026-06-11T00:00:00+00:00",
        "sources": [
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
        "proof_candidates": [],
        "warnings": [],
        "profile_facts": {
            "name": "Student Name",
            "school": "Verified University",
            "email": "student@example.dev",
        },
    }), encoding="utf-8")
    monkeypatch.setattr(profile_harness, "PROFILE_SOURCE_CACHE_PATH", cache_path)

    report = build_profile_harness_report(
        "Website: https://example.dev",
        structured_profile={
            "name": "Student Name",
            "school": "Example University",
            "email": "student@example.dev",
            "background_summary": "Systems student.",
            "proof_points": [],
            "interests": ["inference systems"],
        },
    )

    assert report["profile_name"] == "Student Name"
    assert report["school"] == "Verified University"
    assert [source["kind"] for source in report["sources"]] == ["web", "resume", "github", "linkedin"]
    assert not any(
        source["kind"] == "resume" and source["status"] == "optional"
        for source in report["sources"]
    )
