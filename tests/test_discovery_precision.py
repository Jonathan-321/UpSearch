"""Tests for discovery freshness and lane precision (task 028).

Covers:
- HN Algolia freshness bound (numericFilters on created_at_i)
- Lane alias expansion (ai_infrastructure_and_inference and variants)
- Lane-signal gating of HN/Reddit-derived candidates
- Launch HN / Show HN / is-hiring escape hatch with a weaker title bar
- Reddit 403: explicit empty, one info log per run, no exception
"""

import logging
import time
from typing import Any

from upsearch import auto_discovery
from upsearch.sourcing import hackernews, reddit
from upsearch.sourcing.base import Post


# ── HN freshness bound ────────────────────────────────────────────────────────


def test_hn_search_sends_freshness_bound(monkeypatch) -> None:
    """The default Algolia query carries a created_at_i lower bound."""
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "upsearch.sourcing.hackernews.requests.get",
        _capture_get(captured, {"hits": []}),
    )

    lo = int(time.time()) - hackernews.DEFAULT_MAX_AGE_DAYS * 86400
    posts = hackernews.search("LLM inference", limit=5)
    hi = int(time.time()) - hackernews.DEFAULT_MAX_AGE_DAYS * 86400

    assert posts == []
    assert len(captured) == 1
    numeric = captured[0]["params"].get("numericFilters", "")
    assert numeric.startswith("created_at_i>")
    cutoff = int(numeric.split(">")[1])
    assert lo <= cutoff <= hi


def test_hn_search_freshness_override_and_disable(monkeypatch) -> None:
    """max_age_days overrides the bound; None disables it entirely."""
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "upsearch.sourcing.hackernews.requests.get",
        _capture_get(captured, {"hits": []}),
    )

    lo = int(time.time()) - 30 * 86400
    hackernews.search("LLM inference", limit=5, max_age_days=30)
    hi = int(time.time()) - 30 * 86400
    cutoff = int(captured[0]["params"]["numericFilters"].split(">")[1])
    assert lo <= cutoff <= hi

    captured.clear()
    hackernews.search("LLM inference", limit=5, max_age_days=None)
    assert "numericFilters" not in captured[0]["params"]


def test_hn_job_query_bounds_both_requests(monkeypatch) -> None:
    """Job-style queries hit story and ask_hn; both carry the bound."""
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "upsearch.sourcing.hackernews.requests.get",
        _capture_get(captured, {"hits": []}),
    )

    hackernews.search("hiring inference", limit=5)

    assert len(captured) == 2
    for call in captured:
        assert call["params"].get("numericFilters", "").startswith("created_at_i>")


# ── Lane alias expansion ──────────────────────────────────────────────────────


def test_lane_alias_resolves_to_mapped_lanes() -> None:
    expected = ["ai_infra", "inference_systems"]
    assert auto_discovery.resolve_lanes("ai_infrastructure_and_inference") == expected
    assert auto_discovery.resolve_lanes("AI Infrastructure and Inference") == expected
    assert auto_discovery.resolve_lanes("ai-infrastructure-and-inference") == expected
    # Canonical lanes (and their space/hyphen variants) stay single lanes
    assert auto_discovery.resolve_lanes("ai_infra") == ["ai_infra"]
    assert auto_discovery.resolve_lanes("AI Infra") == ["ai_infra"]
    # Unknown lanes pass through unchanged (literal-keyword degrade preserved)
    assert auto_discovery.resolve_lanes("quantum networking") == ["quantum networking"]


def test_discover_alias_lane_searches_and_merges_mapped_lanes(monkeypatch) -> None:
    queried: list[str] = []

    def fake_hn(query: str, limit: int = 5, **_kwargs: Any) -> list:
        queried.append(query)
        return []

    monkeypatch.setattr(auto_discovery.hackernews, "search", fake_hn)
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(
        auto_discovery,
        "rss_search",
        lambda **_kwargs: [
            {
                "title": "InferStack launches an LLM inference platform",
                "summary": "GPU model serving with lower latency.",
                "link": "https://example.com/inferstack",
                "source": "techcrunch_startups",
                "company_name": "InferStack",
            },
            {
                "title": "RackForge raises for GPU cloud infrastructure",
                "summary": "AI infrastructure for training clusters.",
                "link": "https://example.com/rackforge",
                "source": "techcrunch_startups",
                "company_name": "RackForge",
            },
        ],
    )

    results = auto_discovery.discover("ai_infrastructure_and_inference", limit=8)
    names = [c.name for c in results]

    # Keywords from both mapped lanes were searched
    assert any("AI infrastructure" in q for q in queried)
    assert any("inference" in q.lower() for q in queried)
    # Candidates from both mapped lanes merge into one ranked list
    assert "RackForge" in names
    assert "InferStack" in names
    # A company matching both mapped lanes deduplicates to one candidate
    assert names.count("InferStack") == 1


# ── Lane-signal gating of HN/Reddit candidates ────────────────────────────────


def test_off_lane_hn_candidate_dropped_lane_matched_kept(monkeypatch) -> None:
    posts = [
        Post(
            title="Zest — a restaurant discovery app",
            body="Find restaurants based on where friends eat.",
            url="https://example.com/zest",
            source="hackernews",
        ),
        Post(
            title="Tensorline — fastest LLM inference engine",
            body="Serving stack for low-latency GPU inference.",
            url="https://example.com/tensorline",
            source="hackernews",
        ),
    ]
    _patch_sources(monkeypatch, hn=posts)

    candidates = auto_discovery.discover("inference_systems", limit=8)
    names = [c.name for c in candidates]

    assert "Tensorline" in names
    assert "Zest" not in names
    # The unverified-candidate fallback is preserved for gated-in posts
    kept = next(c for c in candidates if c.name == "Tensorline")
    assert kept.identity_status == "discovered"
    assert "unverified" in kept.source_labels


def test_reddit_candidates_are_lane_gated_too(monkeypatch) -> None:
    posts = [
        Post(
            title="Zest — a restaurant discovery app",
            body="Where do you eat?",
            url="https://reddit.com/r/startups/1",
            source="reddit",
            subreddit="startups",
        ),
        Post(
            title="Tensorline — fastest LLM inference engine",
            body="Benchmarks inside.",
            url="https://reddit.com/r/MachineLearning/2",
            source="reddit",
            subreddit="MachineLearning",
        ),
    ]
    _patch_sources(monkeypatch, reddit_posts=posts)

    names = [c.name for c in auto_discovery.discover("inference_systems", limit=8)]

    assert "Tensorline" in names
    assert "Zest" not in names


def test_launch_hn_escape_hatch_requires_a_lane_term(monkeypatch) -> None:
    posts = [
        Post(
            title="Launch HN: FooCloud (YC W26) – GPU clusters for ML teams",
            body="",
            url="https://example.com/foocloud",
            source="hackernews",
        ),
        Post(
            title="Launch HN: PetMatch (YC W26) – marketplace for pet sitters",
            body="",
            url="https://example.com/petmatch",
            source="hackernews",
        ),
    ]
    _patch_sources(monkeypatch, hn=posts)

    names = [c.name for c in auto_discovery.discover("ai_infra", limit=8)]

    # No full lane phrase in the title, but the launch marker + a lane term
    # ("GPU", "ML") passes the weaker bar
    assert "FooCloud" in names
    # A launch post with zero lane terms stays out
    assert "PetMatch" not in names


def test_is_hiring_marker_uses_weaker_title_bar() -> None:
    on_lane = Post(title="Acme is hiring GPU engineers", body="", url="", source="hackernews")
    off_lane = Post(title="Acme is hiring sous chefs", body="", url="", source="hackernews")
    plain_off_lane = Post(title="Acme ships a GPU dashboard theme pack", body="", url="", source="reddit")

    assert auto_discovery._passes_post_lane_gate("ai_infra", on_lane)
    assert not auto_discovery._passes_post_lane_gate("ai_infra", off_lane)
    # Without a marker, a stray lane term alone does not satisfy the full bar
    assert not auto_discovery._passes_post_lane_gate("inference_systems", plain_off_lane)


# ── Reddit 403 handling ───────────────────────────────────────────────────────


def test_reddit_403_returns_empty_and_logs_once(monkeypatch, caplog) -> None:
    monkeypatch.setattr(reddit, "_blocked_logged", False)
    captured: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "upsearch.sourcing.reddit.requests.get",
        _capture_get(captured, {}, status_code=403),
    )

    with caplog.at_level(logging.INFO, logger="upsearch.sourcing.reddit"):
        posts = reddit.search("LLM inference", limit=3)

    assert posts == []
    assert len(captured) == len(reddit.RESEARCH_SUBREDDITS)
    # old.reddit host and a browser-style UA on every request
    for call in captured:
        assert call["url"].startswith("https://old.reddit.com/")
        assert call["headers"]["User-Agent"].startswith("Mozilla/5.0")
    # Blocked state surfaces once per run, not once per subreddit
    blocked = [r for r in caplog.records if "Reddit search blocked" in r.getMessage()]
    assert len(blocked) == 1


# ── Helpers ───────────────────────────────────────────────────────────────────


class _FakeResponse:
    """Minimal requests-like response stub."""

    def __init__(self, data: Any, status_code: int = 200) -> None:
        self.status_code = status_code
        self._data = data

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


def _capture_get(captured: list[dict[str, Any]], data: Any, status_code: int = 200):
    """Build a requests.get replacement that records each call."""

    def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
        captured.append({"url": url, **kwargs})
        return _FakeResponse(data, status_code=status_code)

    return fake_get


def _rejected_identity(**kwargs: Any) -> Any:
    """Identity stub: never verified, so the unverified fallback path runs."""
    name = kwargs.get("name", "")
    urls = kwargs.get("evidence_urls", []) or []

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


def _patch_sources(
    monkeypatch,
    hn: list[Post] | None = None,
    reddit_posts: list[Post] | None = None,
) -> None:
    """Pin every discovery source to fixed data; no network, no identity HTTP."""
    monkeypatch.setattr(auto_discovery.hackernews, "search", lambda *a, **kw: hn or [])
    monkeypatch.setattr(auto_discovery.reddit, "search", lambda *a, **kw: reddit_posts or [])
    monkeypatch.setattr(auto_discovery.web_search, "search", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "search_github_orgs", lambda *a, **kw: [])
    monkeypatch.setattr(auto_discovery, "rss_search", lambda **kw: [])
    monkeypatch.setattr(auto_discovery, "resolve_company_identity", _rejected_identity)
