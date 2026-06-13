"""Task 026: verifiable people sourcing — author pages and GitHub fallback."""

import json
from unittest.mock import MagicMock

from agents import people as people_agent
from upsearch import github_org_search
from upsearch.sourcing import company_people


BLOG_INDEX = """
<a href="/blog/frontier-rl">Frontier RL Is Cheaper Than You Think</a>
<a href="/blog/author/jane-doe">Jane Doe</a>
<a href="https://www.fireworks.ai/blog/author/wei-chen?page=2#top">Wei Chen</a>
<a href="https://elsewhere.example/author/foreign">Foreign</a>
"""

AUTHOR_PAGE = """
<title>Posts by Jane Doe | Fireworks</title>
<h1>Jane Doe</h1>
<p>Staff Engineer writing about inference.</p>
"""


def test_author_links_are_discovered_same_domain_only() -> None:
    links = company_people._extract_author_links(
        BLOG_INDEX, "https://www.fireworks.ai/blog", "fireworks.ai"
    )

    assert links == [
        "https://www.fireworks.ai/blog/author/jane-doe",
        "https://www.fireworks.ai/blog/author/wei-chen",
    ]


def test_blog_index_yields_author_page_candidates(monkeypatch) -> None:
    pages = {
        "https://www.fireworks.ai/blog": BLOG_INDEX,
        "https://www.fireworks.ai/blog/author/jane-doe": AUTHOR_PAGE,
        "https://www.fireworks.ai/blog/author/wei-chen": "<title>Wei Chen – Fireworks Blog</title>",
    }
    monkeypatch.setattr(company_people, "_fetch_page", lambda url: pages.get(url, ""))

    candidates = company_people.fetch_company_people(
        "fireworks.ai", ["https://www.fireworks.ai/blog"]
    )

    names = [c["name"] for c in candidates]
    assert "Jane Doe" in names
    assert "Wei Chen" in names
    jane = next(c for c in candidates if c["name"] == "Jane Doe")
    assert jane["source_url"] == "https://www.fireworks.ai/blog/author/jane-doe"


def test_github_fallback_triggers_on_verified_scarcity(monkeypatch) -> None:
    org_calls: list[str] = []

    monkeypatch.setattr(people_agent.hackernews, "search", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "fetch_company_people", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "find_company_org", lambda name, domain, candidates=None: "fw-ai")
    monkeypatch.setattr(people_agent, "_fallback_people", lambda *a, **k: [])

    def fake_org_members(company, org, problem_keywords=None):
        org_calls.append(org)
        return [{
            "name": "Dmytro Dzhulgakov",
            "role": "GitHub contributor at Fireworks",
            "proximity": "engineer",
            "source_url": "https://github.com/dzhulgakov",
            "relevance_score": 7,
            "relevance_reason": "GitHub contributor to fireworks-ai",
        }]

    monkeypatch.setattr(people_agent, "search_org_members", fake_org_members)
    # Model proposes plausible names that all fail verification.
    monkeypatch.setattr(
        people_agent.llm,
        "complete",
        lambda **kwargs: json.dumps({"people": [
            {"name": "Liangchen Luo", "role": "CTO", "source_url": "https://www.fireworks.ai/about"},
        ]}),
    )
    monkeypatch.setattr(
        people_agent,
        "verify_people",
        lambda people, company: [
            {**p, "verification_status": "verified" if "github.com" in str(p.get("source_url")) else "unverified"}
            for p in people
        ],
    )

    out = people_agent.run("Fireworks", {"title": "inference"}, {"skills": []})
    people = out["result"]["people"]

    assert org_calls == ["fw-ai"]
    verified = [p["name"] for p in people if p["verification_status"] == "verified"]
    assert verified == ["Dmytro Dzhulgakov"]
    # The unverifiable model candidate is kept for research context.
    assert "Liangchen Luo" in [p["name"] for p in people]


def test_github_fallback_skipped_when_enough_verified(monkeypatch) -> None:
    monkeypatch.setattr(people_agent.hackernews, "search", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "fetch_company_people", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "_fallback_people", lambda *a, **k: [])
    monkeypatch.setattr(
        people_agent,
        "find_company_org",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("github path must not run")),
    )
    monkeypatch.setattr(
        people_agent.llm,
        "complete",
        lambda **kwargs: json.dumps({"people": [
            {"name": "Jane Doe", "role": "Engineer", "source_url": "https://x.example/a"},
            {"name": "Wei Chen", "role": "Engineer", "source_url": "https://x.example/b"},
        ]}),
    )
    monkeypatch.setattr(
        people_agent,
        "verify_people",
        lambda people, company: [{**p, "verification_status": "verified"} for p in people],
    )

    out = people_agent.run("Acme", {"title": "x"}, {"skills": []})

    assert len(out["result"]["people"]) == 2


def _gh_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    return resp


def test_org_search_falls_back_to_repo_contributors(monkeypatch) -> None:
    monkeypatch.setattr(github_org_search, "resolve_org_url", lambda org: f"https://github.com/{org}")

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/fireworks-ai/members"):
            return _gh_response([])
        if url.endswith("/orgs/fireworks-ai/repos"):
            return _gh_response([{"name": "inference-engine"}])
        if url.endswith("/repos/fireworks-ai/inference-engine/contributors"):
            return _gh_response([
                {"login": "dzhulgakov"},
                {"login": "dependabot[bot]"},
            ])
        if url.endswith("/users/dzhulgakov"):
            return _gh_response({"name": "Dmytro Dzhulgakov", "bio": "Inference"})
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        github_org_search.httpx,
        "Client",
        lambda **kwargs: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    people = github_org_search.search_org_members("Fireworks", "fireworks-ai")

    assert [p["name"] for p in people] == ["Dmytro Dzhulgakov"]
    assert people[0]["source"] == "github_repo_contributor"
    # Verification status is never pre-claimed; the evidence pipeline decides.
    assert "verification_status" not in people[0]


def test_find_company_org_requires_metadata_match(monkeypatch) -> None:
    """Bare org existence is not ownership: "fireworks" exists but is not the
    company; "fw-ai" wins because its website matches the verified domain."""

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/fireworks"):
            return _gh_response({"name": "Fireworks Photo App", "blog": "https://photos.example"})
        if url.endswith("/orgs/fireworks-ai"):
            # Name-identical org owned by a DIFFERENT company: domain veto.
            return _gh_response({"name": "Fireworks!", "blog": "fireworks-ai.com"})
        if url.endswith("/orgs/fireworksai"):
            return _gh_response({}, status=404)
        if url.endswith("/search/users"):
            return _gh_response({"items": [{"login": "fw-ai"}]})
        if url.endswith("/orgs/fw-ai"):
            return _gh_response({"name": "Fireworks AI", "blog": "https://fireworks.ai"})
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        github_org_search.httpx,
        "Client",
        lambda **kwargs: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    org = github_org_search.find_company_org(
        "Fireworks", "www.fireworks.ai",
        candidates=["fireworks", "fireworks-ai", "fireworksai"],
    )

    assert org == "fw-ai"


def test_display_names_lose_parentheticals() -> None:
    assert github_org_search._clean_display_name("Yufei (Benny) Chen") == "Yufei Chen"
    assert github_org_search._clean_display_name("Tran Le") == "Tran Le"


def test_github_evidence_verifies_via_api_documents(monkeypatch) -> None:
    """Profile HTML often cannot name the company; the contributors listing
    plus the org's declared website are the public documents that can."""
    from upsearch import person_verification

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/fw-ai"):
            return _gh_response({"name": "Fireworks AI", "blog": "https://fireworks.ai"})
        if url.endswith("/repos/fw-ai/cookbook/contributors"):
            return _gh_response([{"login": "pgarbacki"}, {"login": "other"}])
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        person_verification,
        "_client",
        lambda: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    person = {
        "name": "Pawel Garbacki",
        "role": "GitHub contributor at Fireworks",
        "source_url": "https://github.com/pgarbacki",
        "github_url": "https://github.com/pgarbacki",
        "github_evidence": {
            "org": "fw-ai", "repo": "cookbook", "login": "pgarbacki",
            "company_domain": "fireworks.ai",
        },
    }
    result = person_verification.verify_person(person, "Fireworks")

    assert result["verification_status"] == "verified"
    assert result["verification_reason"] == "github_contributor_listing_confirmed"
    assert result["github_url"] == "https://github.com/pgarbacki"


def test_github_evidence_rejects_when_login_absent_or_org_mismatched(monkeypatch) -> None:
    from upsearch import person_verification

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/fw-ai"):
            return _gh_response({"name": "Fireworks AI", "blog": "https://fireworks.ai"})
        if url.endswith("/orgs/impostor"):
            return _gh_response({"name": "Fireworks!", "blog": "https://fireworks-ai.com"})
        if url.endswith("/repos/fw-ai/cookbook/contributors"):
            return _gh_response([{"login": "someone-else"}])
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        person_verification,
        "_client",
        lambda: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    absent = person_verification.verify_person({
        "name": "Pawel Garbacki",
        "source_url": "https://github.com/pgarbacki",
        "github_evidence": {"org": "fw-ai", "repo": "cookbook", "login": "pgarbacki2",
                            "company_domain": "fireworks.ai"},
    }, "Fireworks")
    assert absent["verification_status"] == "unverified"
    assert absent["verification_reason"] == "github_contributor_not_in_listing"

    mismatched = person_verification.verify_person({
        "name": "Pawel Garbacki",
        "source_url": "https://github.com/pgarbacki",
        "github_evidence": {"org": "impostor", "repo": "cookbook", "login": "pgarbacki",
                            "company_domain": "fireworks.ai"},
    }, "Fireworks")
    assert mismatched["verification_status"] == "unverified"
    assert mismatched["verification_reason"] == "github_org_company_mismatch"


CITED_POST = """
<article>
<h1>The Baseten Inference Stack</h1>
<a href="/blog/author/amir-h">By Amir</a>
</article>
"""

CITED_AUTHOR_PAGE = "<title>Posts by Amir Haghighat | Baseten</title>"


def test_author_from_post_url_prefers_author_page(monkeypatch) -> None:
    pages = {
        "https://www.baseten.co/resources/guide/inference-stack": CITED_POST,
        "https://www.baseten.co/blog/author/amir-h": CITED_AUTHOR_PAGE,
    }
    monkeypatch.setattr(company_people, "_fetch_page", lambda url: pages.get(url, ""))

    author = company_people.author_from_post_url(
        "https://www.baseten.co/resources/guide/inference-stack", "baseten.co"
    )

    assert author is not None
    assert author["name"] == "Amir Haghighat"
    assert author["relevance_score"] == 10
    assert author["proximity"] == "author"
    assert author["cited_source_url"] == "https://www.baseten.co/resources/guide/inference-stack"


def test_author_from_post_url_off_domain_returns_none() -> None:
    assert company_people.author_from_post_url("https://elsewhere.example/post", "baseten.co") is None


def test_cited_authors_lead_the_people_pool(monkeypatch) -> None:
    monkeypatch.setattr(people_agent.hackernews, "search", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "fetch_company_people", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "find_company_org", lambda *a, **k: None)
    monkeypatch.setattr(people_agent, "_fallback_people", lambda *a, **k: [])
    monkeypatch.setattr(
        people_agent,
        "author_from_post_url",
        lambda url, domain: {
            "name": "Amir Haghighat",
            "role": "Technical author",
            "proximity": "author",
            "source_url": "https://www.baseten.co/blog/author/amir-h",
            "relevance_score": 10,
            "relevance_reason": "Wrote the source this packet cites.",
            "cited_source_url": url,
        },
    )
    monkeypatch.setattr(
        people_agent.llm,
        "complete",
        lambda **kwargs: json.dumps({"people": [
            {"name": "Jane Doe", "role": "Engineer", "source_url": "https://x.example/a"},
            {"name": "Wei Chen", "role": "Engineer", "source_url": "https://x.example/b"},
        ]}),
    )
    monkeypatch.setattr(
        people_agent,
        "verify_people",
        lambda people, company: [{**p, "verification_status": "verified"} for p in people],
    )

    out = people_agent.run(
        "Baseten",
        {"title": "inference", "source_urls": ["https://www.baseten.co/resources/guide/inference-stack"]},
        {"skills": []},
        company_domain="baseten.co",
    )
    people = out["result"]["people"]

    assert people[0]["name"] == "Amir Haghighat"
    assert people[0]["relevance_score"] == 10


def test_cited_author_replaces_same_name_model_proposal(monkeypatch) -> None:
    """A model's about-page claim of the same person must not shadow the
    cited-author record, which carries strictly better evidence."""
    monkeypatch.setattr(people_agent.hackernews, "search", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "fetch_company_people", lambda *a, **k: [])
    monkeypatch.setattr(people_agent, "find_company_org", lambda *a, **k: None)
    monkeypatch.setattr(people_agent, "_fallback_people", lambda *a, **k: [])
    monkeypatch.setattr(
        people_agent,
        "author_from_post_url",
        lambda url, domain: {
            "name": "Amir Haghighat",
            "role": "Technical author",
            "proximity": "author",
            "source_url": "https://www.baseten.co/author/amir-haghighat",
            "relevance_score": 10,
            "relevance_reason": "Wrote the source this packet cites.",
            "cited_source_url": url,
        },
    )
    monkeypatch.setattr(
        people_agent.llm,
        "complete",
        lambda **kwargs: json.dumps({"people": [
            {"name": "Amir Haghighat", "role": "Co-founder & CTO",
             "source_url": "https://www.baseten.co/about", "relevance_score": 9},
        ]}),
    )
    monkeypatch.setattr(
        people_agent,
        "verify_people",
        lambda people, company: [{**p, "verification_status": "verified"} for p in people],
    )

    out = people_agent.run(
        "Baseten",
        {"title": "inference", "source_urls": ["https://www.baseten.co/blog/post"]},
        {"skills": []},
        company_domain="baseten.co",
    )
    people = out["result"]["people"]

    amirs = [p for p in people if p["name"] == "Amir Haghighat"]
    assert len(amirs) == 1
    assert amirs[0]["proximity"] == "author"
    assert amirs[0]["source_url"] == "https://www.baseten.co/author/amir-haghighat"


def test_repo_ranking_prefers_problem_matched_repo(monkeypatch) -> None:
    monkeypatch.setattr(github_org_search, "resolve_org_url", lambda org: f"https://github.com/{org}")

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/fw-ai/members"):
            return _gh_response([])
        if url.endswith("/orgs/fw-ai/repos"):
            return _gh_response([
                {"name": "marketing-site", "description": "Company website", "topics": []},
                {"name": "inference-engine", "description": "LLM inference serving runtime", "topics": ["gpu"]},
            ])
        if url.endswith("/repos/fw-ai/inference-engine/contributors"):
            return _gh_response([{"login": "dzhulgakov"}])
        if url.endswith("/repos/fw-ai/marketing-site/contributors"):
            return _gh_response([{"login": "webdev"}])
        if url.endswith("/users/dzhulgakov"):
            return _gh_response({"name": "Dmytro Dzhulgakov", "bio": ""})
        if url.endswith("/users/webdev"):
            return _gh_response({"name": "Web Devlin", "bio": ""})
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        github_org_search.httpx,
        "Client",
        lambda **kwargs: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    people = github_org_search.search_org_members(
        "Fireworks", "fw-ai", problem_keywords=["inference", "serving", "latency"]
    )

    top = people[0]
    assert top["name"] == "Dmytro Dzhulgakov"
    assert top["relevance_score"] == 8
    assert "inference-engine" in top["relevance_reason"]
    assert top["github_evidence"]["repo"] == "inference-engine"


def test_verification_memo_dedupes_org_fetches(monkeypatch) -> None:
    from upsearch import person_verification

    call_log: list[str] = []

    def fake_get(url, **kwargs):
        call_log.append(url)
        if url.endswith("/orgs/fw-ai"):
            return _gh_response({"name": "Fireworks AI", "blog": "https://fireworks.ai"})
        if url.endswith("/repos/fw-ai/cookbook/contributors"):
            return _gh_response([{"login": "a-dev"}, {"login": "b-dev"}, {"login": "c-dev"}])
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        person_verification,
        "_client",
        lambda: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    people = [
        {"name": f"Person {letter.upper()}", "source_url": f"https://github.com/{letter}-dev",
         "github_evidence": {"org": "fw-ai", "repo": "cookbook", "login": f"{letter}-dev",
                             "company_domain": "fireworks.ai"}}
        for letter in ("a", "b", "c")
    ]
    results = person_verification.verify_people(people, "Fireworks")

    assert all(r["verification_status"] == "verified" for r in results)
    org_fetches = [u for u in call_log if u.endswith("/orgs/fw-ai")]
    listing_fetches = [u for u in call_log if u.endswith("/contributors")]
    assert len(org_fetches) == 1
    assert len(listing_fetches) == 1


def test_author_page_evidence_verifies_cited_author(monkeypatch) -> None:
    from upsearch import person_verification

    monkeypatch.setattr(
        person_verification,
        "fetch_source_text",
        lambda url: "<title>Posts by Amir Haghighat | Baseten</title><h1>Amir Haghighat</h1>",
    )

    person = {
        "name": "Amir Haghighat",
        "role": "Technical author",
        "source_url": "https://www.baseten.co/author/amir-haghighat",
        "author_page_evidence": {
            "url": "https://www.baseten.co/author/amir-haghighat",
            "company_domain": "www.baseten.co",
        },
    }
    result = person_verification.verify_person(person, "Baseten")

    assert result["verification_status"] == "verified"
    assert result["verification_reason"] == "author_page_title_confirmed"


def test_author_page_evidence_rejects_wrong_name_or_domain(monkeypatch) -> None:
    from upsearch import person_verification

    monkeypatch.setattr(
        person_verification,
        "fetch_source_text",
        lambda url: "<title>Posts by Someone Else | Baseten</title>",
    )

    wrong_name = person_verification.verify_person({
        "name": "Amir Haghighat",
        "source_url": "https://www.baseten.co/author/someone-else",
        "author_page_evidence": {
            "url": "https://www.baseten.co/author/someone-else",
            "company_domain": "baseten.co",
        },
    }, "Baseten")
    assert wrong_name["verification_status"] == "unverified"
    assert wrong_name["verification_reason"] == "author_page_does_not_name_person"

    off_domain = person_verification.verify_person({
        "name": "Amir Haghighat",
        "source_url": "https://elsewhere.example/author/amir",
        "author_page_evidence": {
            "url": "https://elsewhere.example/author/amir",
            "company_domain": "baseten.co",
        },
    }, "Baseten")
    assert off_domain["verification_status"] == "unverified"
    assert off_domain["verification_reason"] == "author_page_off_domain"


def test_org_name_guesses_strip_suffix_before_dashing() -> None:
    assert people_agent._org_name_guesses("Together AI") == ["together", "together-ai", "togetherai"]
    assert people_agent._org_name_guesses("Baseten")[0] == "baseten"


def test_site_declared_org_wins_without_name_match(monkeypatch) -> None:
    """A company site linking github.com/<org> declares ownership; no display
    name or blog match required (togethercomputer has neither)."""
    monkeypatch.setattr(
        github_org_search,
        "orgs_from_company_site",
        lambda domain: ["togethercomputer"],
    )

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/togethercomputer"):
            return _gh_response({"name": "Together", "blog": None})
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        github_org_search.httpx,
        "Client",
        lambda **kwargs: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    org = github_org_search.find_company_org(
        "Together AI", "www.together.ai", candidates=["together"]
    )

    assert org == "togethercomputer"


def test_site_declared_org_still_domain_vetoed(monkeypatch) -> None:
    monkeypatch.setattr(
        github_org_search,
        "orgs_from_company_site",
        lambda domain: ["impostor"],
    )

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/impostor"):
            return _gh_response({"name": "Together", "blog": "https://impostor.example"})
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        github_org_search.httpx,
        "Client",
        lambda **kwargs: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    org = github_org_search.find_company_org("Together AI", "www.together.ai", candidates=[])

    assert org is None


def test_github_evidence_accepts_site_declared_org(monkeypatch) -> None:
    from upsearch import person_verification

    monkeypatch.setattr(
        "upsearch.github_org_search.orgs_from_company_site",
        lambda domain: ["togethercomputer"],
    )

    def fake_get(url, **kwargs):
        if url.endswith("/orgs/togethercomputer"):
            return _gh_response({"name": "Together", "blog": None})
        if url.endswith("/repos/togethercomputer/flash-attn/contributors"):
            return _gh_response([{"login": "tri-dao"}])
        return _gh_response({}, status=404)

    client = MagicMock()
    client.get.side_effect = fake_get
    monkeypatch.setattr(
        person_verification,
        "_client",
        lambda: MagicMock(__enter__=lambda s: client, __exit__=lambda s, *a: False),
    )

    result = person_verification.verify_person({
        "name": "Tri Dao",
        "source_url": "https://github.com/tri-dao",
        "github_evidence": {"org": "togethercomputer", "repo": "flash-attn", "login": "tri-dao",
                            "company_domain": "www.together.ai"},
    }, "Together AI")

    assert result["verification_status"] == "verified"
    assert result["verification_reason"] == "github_contributor_listing_confirmed"
