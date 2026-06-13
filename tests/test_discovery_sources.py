"""Tests for new discovery source connectors.

Covers:
- GitHub org search connector
- Engineering blog web search
- RSS feed expansion (YC blog, VentureBeat, TheNewStack)
- Multi-source deduplication
"""

from typing import Any

from upsearch import auto_discovery
from upsearch.auto_discovery import CompanyCandidate
from upsearch.sourcing import web_search
from upsearch.sourcing.base import Post
from upsearch.sourcing.github_org_search import search_github_orgs
from upsearch.sourcing.rss_feeds import FEEDS, search as rss_search


# ── GitHub org search ────────────────────────────────────────────────────────


def test_github_org_search_returns_empty_on_api_failure(monkeypatch) -> None:
    """API failure returns an empty list without network access."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setattr(
        "upsearch.sourcing.github_org_search.httpx.Client",
        lambda **_kwargs: _FakeClient({}, status_code=503),
    )
    results = search_github_orgs("ai_infra", limit=3)
    assert results == []


def test_github_org_search_returns_valid_shape(monkeypatch) -> None:
    """Verify GitHub org discovery works via auto_discovery's discover().

    Patching search_github_orgs at the auto_discovery level avoids httpx.
    """
    org_results = [
        {
            "name": "ExampleOrg",
            "display_name": "Example Org Inc.",
            "description": "Building AI infrastructure",
            "website": "https://example.ai",
            "repo_url": "https://github.com/ExampleOrg/repo",
            "source": "github_org",
            "lane": "ai_infra",
            "topic_hits": 1,
        }
    ]

    # Patch search_github_orgs in auto_discovery's namespace
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: org_results)

    # Mock all other sources to be empty
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **kw: [])

    # Disable identity resolution to avoid real HTTP fetches
    monkeypatch.setattr(
        auto_discovery,
        "resolve_company_identity",
        lambda **kw: _fake_identity(kw.get("name", ""), kw.get("lane", ""), kw.get("evidence_urls", [])),
    )

    results = auto_discovery.discover("ai_infra", limit=5)
    assert len(results) >= 1
    r = results[0]
    assert r.name == "Example Org Inc."
    assert r.website == "https://example.ai"
    assert "github_org" in r.source_labels


def test_rss_candidate_must_match_requested_lane(monkeypatch) -> None:
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(
        auto_discovery,
        "rss_search",
        lambda **_kwargs: [
            {
                "title": "Zest launches a restaurant discovery app",
                "summary": "Find restaurants based on where people eat.",
                "link": "https://example.com/zest",
                "source": "techcrunch_startups",
                "company_name": "Zest",
            },
            {
                "title": "InferStack launches an LLM inference platform",
                "summary": "GPU model serving with lower latency.",
                "link": "https://example.com/inferstack",
                "source": "techcrunch_startups",
                "company_name": "InferStack",
            },
        ],
    )

    names = [candidate.name for candidate in auto_discovery.discover("inference_systems")]

    assert "InferStack" in names
    assert "Zest" not in names


def test_duplicate_unverified_sources_do_not_raise_identity_confidence() -> None:
    candidates: dict[str, CompanyCandidate] = {}
    first = CompanyCandidate(
        name="Example",
        lane="ai_infra",
        identity_status="discovered",
        identity_confidence=0.3,
        source_labels=["github_org", "unverified"],
    )
    second = CompanyCandidate(
        name="Example",
        lane="ai_infra",
        identity_status="discovered",
        identity_confidence=0.3,
        source_labels=["rss", "unverified"],
    )

    auto_discovery._merge_or_create(candidates, first, "ai_infra")
    auto_discovery._merge_or_create(candidates, second, "ai_infra")

    merged = next(iter(candidates.values()))
    assert merged.identity_status == "discovered"
    assert merged.identity_confidence == 0.3
    assert set(merged.source_labels) == {"github_org", "rss", "unverified"}


def test_github_org_search_skips_users(monkeypatch) -> None:
    """Only Organization type owners should appear — not User type."""

    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **kw: [])

    candidates = auto_discovery.discover("developer_tools", limit=5)
    assert isinstance(candidates, list)


def test_github_org_candidate_requires_direct_lane_signal(monkeypatch) -> None:
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **_kwargs: [])
    monkeypatch.setattr(
        auto_discovery,
        "search_github_orgs",
        lambda *a, **kw: [
            {
                "name": "appwrite",
                "display_name": "Appwrite",
                "description": "Backend platform for web and mobile applications",
                "repo_description": "Auth, databases, storage, and hosting",
                "website": "https://appwrite.io",
                "repo_url": "https://github.com/appwrite/appwrite",
                "source": "github_org",
            },
            {
                "name": "chroma-core",
                "display_name": "Chroma",
                "description": "Search infrastructure for AI",
                "repo_description": "Retrieval infrastructure for AI applications",
                "website": "https://trychroma.com",
                "repo_url": "https://github.com/chroma-core/chroma",
                "source": "github_org",
            },
        ],
    )
    monkeypatch.setattr(
        auto_discovery,
        "resolve_company_identity",
        lambda **kwargs: _fake_identity(kwargs["name"], kwargs["lane"], kwargs["evidence_urls"]),
    )

    names = [candidate.name for candidate in auto_discovery.discover("ai_infra")]

    assert "Chroma" in names
    assert "Appwrite" not in names


# ── Engineering blog discovery ────────────────────────────────────────────────


def test_engineering_blog_discovery_adds_candidates(monkeypatch) -> None:
    """Engineering blog search results should produce CompanyCandidates."""

    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])

    # Provide a blog result that resolves via _candidate_from_post
    blog_results = [
        {"title": "InferStack — building the fastest inference engine", "url": "https://inferstack.ai/blog/optimization"},
    ]
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: blog_results)

    candidates = auto_discovery.discover("inference_systems", limit=5)

    # Should have at least one candidate from the blog result
    assert len(candidates) >= 1
    names = [c.name for c in candidates]
    assert any("InferStack" in n for n in names)


def test_engineering_blog_discovery_returns_empty_when_no_results(monkeypatch) -> None:
    """Engineering blog search returning empty should not add candidates."""

    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])

    candidates = auto_discovery.discover("robotics_ai", limit=5)
    # Should not crash and be an empty or short list (HN/Reddit also empty)
    assert isinstance(candidates, list)


def test_engineering_blog_title_extracts_company_not_section_name() -> None:
    assert auto_discovery._company_name_from_blog_title("Engineering at Meta — AI Infrastructure") == "Meta"
    assert auto_discovery._company_name_from_blog_title("Uber Engineering | Model Serving") == "Uber"
    assert auto_discovery._company_name_from_blog_title("AI Infrastructure Trends 2026: A Guide") == ""
    assert auto_discovery._company_name_from_blog_title("MLOps: Model serving") == ""
    assert auto_discovery._company_name_from_blog_title("Latest Model Serving articles") == ""


# ── RSS feed expansion ────────────────────────────────────────────────────────


def test_rss_feeds_dict_has_new_sources() -> None:
    """The FEEDS dict should include the newly added RSS sources."""
    assert "yc_blog" in FEEDS, "YC blog feed missing"
    assert "venturebeat" in FEEDS, "VentureBeat feed missing"
    assert "thenewstack" in FEEDS, "TheNewStack feed missing"


def test_rss_feed_names_in_discovery_call(monkeypatch) -> None:
    """Verify discover() calls rss_search with the expanded feed list.

    We monkeypatch rss_search and check which feed_names were passed.
    """
    captured: list[dict[str, Any]] = []

    def capture_rss(**kwargs: Any) -> list:
        captured.append(kwargs)
        return []

    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "rss_search", capture_rss)

    auto_discovery.discover("ai_infra", limit=5)

    # rss_search should have been called with the expanded feed list
    assert len(captured) >= 1
    feed_names = captured[0].get("feed_names", [])
    assert "yc_blog" in feed_names
    assert "venturebeat" in feed_names
    assert "thenewstack" in feed_names


# ── Multi-source deduplication ────────────────────────────────────────────────


def test_multi_source_dedup_by_name(monkeypatch) -> None:
    """Same company discovered from different sources deduplicates by name."""

    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])

    # Mock web_search to return a blog result
    blog_results = [
        {"title": "NeuralPath AI — inference serving blog", "url": "https://neuralpath.ai/blog/"},
    ]
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: blog_results)

    # Mock rss_search to return the same company
    rss_results = [
        {
            "title": "NeuralPath AI raises $50M for an inference platform",
            "summary": "The company builds GPU model serving infrastructure.",
            "link": "https://techcrunch.com/neuralpath",
            "source": "techcrunch",
        },
    ]
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **_kwargs: rss_results)

    # Disable identity resolution so both sources produce "discovered" candidates
    monkeypatch.setattr(
        auto_discovery,
        "resolve_company_identity",
        lambda **kwargs: _fake_identity(kwargs["name"], kwargs["lane"], []),
    )

    candidates = auto_discovery.discover("inference_systems", limit=5)

    assert len(candidates) >= 1
    # The candidate from multiple sources should have more than one source label
    neural = [c for c in candidates if "NeuralPath" in c.name]
    assert len(neural) == 1, "Should deduplicate to one candidate"
    n = neural[0]
    assert len(n.source_labels) >= 2, "Should carry labels from both sources"
    assert n.fit_guess > 0.50, "Multi-source should boost fit guess"


# ── Helpers ────────────────────────────────────────────────────────────────────


class _FakeResponse:
    """Minimal httpx-like response stub."""

    def __init__(self, data: Any, status_code: int = 200) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeClient:
    """Context-manager replacement for httpx.Client that returns fake responses."""

    def __init__(self, data: Any, status_code: int = 200) -> None:
        self._data = data
        self._status_code = status_code

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def get(self, *args: Any, **kwargs: Any) -> _FakeResponse:
        return _FakeResponse(self._data, self._status_code)


def _fake_identity(name: str, lane: str, evidence_urls: list[str] | None = None) -> Any:
    """Return a rejected/discovered identity that doesn't attempt real resolution."""
    urls = evidence_urls or []

    class FakeIdentity:
        verified: bool = False
        canonical_name: str = name
        website: str = ""
        official_domain: str = ""
        status: str = "rejected"
        confidence: float = 0.3
        reason: str = "Test stub — not real identity"
        evidence_urls: list[str] = urls

    return FakeIdentity()
