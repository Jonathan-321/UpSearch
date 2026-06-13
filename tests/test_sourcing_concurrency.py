"""Concurrency tests for the sourcing connectors.

These verify that the independent network fetches inside each connector now run
on a bounded thread pool (so they overlap) while the public return shapes,
result ordering, dedup, and request counts stay identical to the sequential
behaviour. No real network calls are made — every fetch is mocked, mirroring the
existing sourcing tests.
"""

from __future__ import annotations

import threading
import time
from typing import Any

from upsearch.sourcing import company_people, hackernews, reddit, web_search
from upsearch.sourcing import github_org_search


class _ConcurrencyTracker:
    """Records the peak number of fetches running at the same time."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active = 0
        self.max_active = 0

    def __enter__(self) -> "_ConcurrencyTracker":
        with self._lock:
            self.active += 1
            self.max_active = max(self.max_active, self.active)
        return self

    def __exit__(self, *_args: Any) -> None:
        with self._lock:
            self.active -= 1


class _FakeResp:
    def __init__(self, data: Any, status_code: int = 200) -> None:
        self._data = data
        self.status_code = status_code
        self.text = ""

    def json(self) -> Any:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")


class _FakeClientCM:
    def __init__(self, get_fn) -> None:
        self._get = get_fn

    def __enter__(self) -> "_FakeClientCM":
        return self

    def __exit__(self, *_args: Any) -> bool:
        return False

    def get(self, *args: Any, **kwargs: Any) -> Any:
        return self._get(*args, **kwargs)


_FETCH_DELAY = 0.05


# ── web_search.search_company_problems ───────────────────────────────────────


def test_web_search_problems_runs_queries_concurrently(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()
    calls: list[str] = []

    def fake_search(query: str, limit: int = 5) -> list[dict[str, str]]:
        with tracker:
            calls.append(query)
            time.sleep(_FETCH_DELAY)
        return [
            {"title": query, "url": f"https://ex.example/{query}"},
            {"title": "shared", "url": "https://ex.example/shared"},
        ]

    monkeypatch.setattr(web_search, "search", fake_search)

    results = web_search.search_company_problems("Acme", "ai infra")

    # All four queries ran, and at least two overlapped in time.
    assert len(calls) == 4
    assert tracker.max_active >= 2
    # Query order is preserved in the merged output.
    assert "engineering challenge 2026" in results[0]["title"]
    # Cross-query dedup keeps the shared URL exactly once.
    urls = [r["url"] for r in results]
    assert urls.count("https://ex.example/shared") == 1


# ── company_people.fetch_company_people ──────────────────────────────────────


def test_company_people_fetches_pages_concurrently(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()
    pages = {
        "https://ex.example/a": "<p>By: Alice Zhang</p>",
        "https://ex.example/b": "<p>By: Bob Stone</p>",
        "https://ex.example/c": "<p>By: Carol Diaz</p>",
    }

    def fake_fetch(url: str) -> str:
        with tracker:
            time.sleep(_FETCH_DELAY)
        return pages.get(url, "")

    monkeypatch.setattr(company_people, "_fetch_page", fake_fetch)

    result = company_people.fetch_company_people("ex.example", list(pages))

    assert tracker.max_active >= 2
    # Candidates appear in the original page order (dedup first-wins preserved).
    assert [p["name"] for p in result] == ["Alice Zhang", "Bob Stone", "Carol Diaz"]


# ── reddit.search ────────────────────────────────────────────────────────────


def test_reddit_fetches_subreddits_concurrently_preserving_order(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()

    def fake_get(url: str, **_kwargs: Any) -> _FakeResp:
        with tracker:
            time.sleep(_FETCH_DELAY)
        sub = url.split("/r/")[1].split("/")[0]
        return _FakeResp({"data": {"children": [
            {"data": {"title": f"{sub} post", "permalink": f"/r/{sub}/1"}}
        ]}})

    monkeypatch.setattr(reddit.requests, "get", fake_get)

    posts = reddit.search("inference", subreddits=["a", "b", "c", "d"], limit=5)

    assert tracker.max_active >= 2
    assert [p.subreddit for p in posts] == ["a", "b", "c", "d"]


# ── hackernews.search ────────────────────────────────────────────────────────


def test_hackernews_story_and_ask_run_concurrently(monkeypatch) -> None:
    tracker = _ConcurrencyTracker()
    tags: list[str] = []

    def fake_get(url: str, params: dict | None = None, **_kwargs: Any) -> _FakeResp:
        with tracker:
            time.sleep(_FETCH_DELAY)
        tag = (params or {})["tags"]
        tags.append(tag)
        return _FakeResp({"hits": [
            {"title": tag, "objectID": "1", "story_text": "body text"}
        ]})

    monkeypatch.setattr(hackernews.requests, "get", fake_get)

    posts = hackernews.search("hiring engineer", limit=5)

    assert set(tags) == {"story", "ask_hn"}
    assert tracker.max_active >= 2
    # Story results lead the output, Ask HN follows (plan order preserved).
    assert posts[0].title == "story"


def test_hackernews_single_request_for_non_job_query(monkeypatch) -> None:
    tags: list[str] = []

    def fake_get(url: str, params: dict | None = None, **_kwargs: Any) -> _FakeResp:
        tags.append((params or {})["tags"])
        return _FakeResp({"hits": []})

    monkeypatch.setattr(hackernews.requests, "get", fake_get)

    hackernews.search("inference", limit=5)

    # No job keyword: only the single story request fires (volume unchanged).
    assert tags == ["story"]


# ── github_org_search.search_github_orgs ─────────────────────────────────────


def test_github_org_search_fetches_profiles_concurrently(monkeypatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    tracker = _ConcurrencyTracker()

    search_payload = {"items": [
        {"owner": {"login": "OrgA", "type": "Organization", "url": "https://api.example/orgs/OrgA"},
         "html_url": "https://gh.example/OrgA/repo", "description": "AI infra"},
        {"owner": {"login": "OrgB", "type": "Organization", "url": "https://api.example/orgs/OrgB"},
         "html_url": "https://gh.example/OrgB/repo", "description": "AI infra"},
        {"owner": {"login": "OrgC", "type": "Organization", "url": "https://api.example/orgs/OrgC"},
         "html_url": "https://gh.example/OrgC/repo", "description": "AI infra"},
    ]}

    def fake_get(url: str, **_kwargs: Any) -> _FakeResp:
        if "/search/repositories" in url:
            return _FakeResp(search_payload)
        with tracker:
            time.sleep(_FETCH_DELAY)
        login = url.rsplit("/", 1)[1]
        return _FakeResp({"type": "Organization", "name": login, "blog": f"https://{login}.example"})

    monkeypatch.setattr(
        github_org_search.httpx, "Client", lambda **_kwargs: _FakeClientCM(fake_get)
    )

    results = github_org_search.search_github_orgs("concurrency_probe_lane", limit=5)

    assert tracker.max_active >= 2
    names = {r["name"] for r in results}
    assert {"OrgA", "OrgB", "OrgC"} <= names
    # Stable insertion order preserved (drives sort tie-breaking).
    assert [r["name"] for r in results][:3] == ["OrgA", "OrgB", "OrgC"]
