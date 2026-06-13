from upsearch import auto_discovery
from upsearch.company_identity import CompanyIdentity
from upsearch.sourcing.base import Post


def verified_identity(name: str, lane: str, url: str) -> CompanyIdentity:
    return CompanyIdentity(
        query_name=name,
        canonical_name=name,
        website="https://example.ai",
        official_domain="example.ai",
        lane=lane,
        status="verified",
        confidence=0.9,
        reason="Evidence agrees.",
        evidence_urls=[url],
        evidence_titles=[name],
    )


def test_discovery_only_emits_verified_candidates(monkeypatch) -> None:
    post = Post(
        title="Show HN: Example AI - an inference serving platform",
        body="",
        url="https://example.ai",
        source="hackernews",
    )
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [post])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **_kwargs: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(
        auto_discovery,
        "resolve_company_identity",
        lambda **kwargs: verified_identity(kwargs["name"], kwargs["lane"], kwargs["evidence_urls"][0]),
    )

    candidates = auto_discovery.discover("inference_systems", limit=3)

    assert len(candidates) == 1
    assert candidates[0].identity_status == "verified"
    assert candidates[0].official_domain == "example.ai"


def test_discovery_preserves_unverified_lead_for_identity_gate(monkeypatch) -> None:
    post = Post(
        title="Show HN: MARS - a robotics platform",
        body="",
        url="https://mars.com",
        source="hackernews",
    )
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [post])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **_kwargs: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(
        auto_discovery,
        "resolve_company_identity",
        lambda **kwargs: CompanyIdentity(
            query_name=kwargs["name"],
            canonical_name=kwargs["name"],
            website="",
            official_domain="",
            lane=kwargs["lane"],
            status="rejected",
            confidence=0.4,
            reason="Ambiguous identity.",
            evidence_urls=kwargs["evidence_urls"],
        ),
    )

    candidates = auto_discovery.discover("robotics_ai", limit=3)

    assert len(candidates) == 1
    assert candidates[0].name == "MARS"
    assert candidates[0].identity_status == "discovered"
    assert candidates[0].official_domain == ""


def test_role_title_is_not_treated_as_company() -> None:
    assert auto_discovery._is_likely_not_a_company("Founding Account Executive")
    assert auto_discovery._is_likely_not_a_company("Open")
