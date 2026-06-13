"""GitHub org discovery — find company GitHub organizations from lane keywords.

Given a technical lane, searches GitHub for public repositories whose
descriptions or topics match lane keywords, then extracts the owning
organization (or user) as a candidate company.

Usage is distinct from ``github_signal``: this module finds *unknown* orgs
as discovery leads; ``github_signal.search_open_problems()`` inspects a
*known* org for technical issues.

Free tier: 60 req/hr unauthenticated, 5000 req/hr with ``GH_TOKEN`` /
``GITHUB_TOKEN``.
"""

from __future__ import annotations

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_GITHUB_API = "https://api.github.com"
_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HEADERS = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "UpSearchGitHubOrgDiscovery/0.1",
}
_MAX_RESULTS = 10
_MAX_PROFILE_WORKERS = 6
_ORG_CACHE: dict[str, list[dict[str, Any]]] = {}


def _auth_headers() -> dict[str, str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return {**_HEADERS, "Authorization": f"Bearer {token}"}
    return _HEADERS


# Mapping from lane to GitHub search query hints
_LANE_QUERIES: dict[str, list[str]] = {
    "ai_infra": [
        "AI infrastructure",
        "ML platform",
        "GPU inference",
        "model serving",
        "machine learning platform",
    ],
    "inference_systems": [
        "LLM inference",
        "model serving",
        "inference engine",
        "GPU inference",
        "deep learning inference",
    ],
    "agentic_ai": [
        "AI agent",
        "agent framework",
        "autonomous agent",
        "LLM agent",
        "agent infrastructure",
    ],
    "developer_tools": [
        "developer tools",
        "devtools",
        "developer platform",
        "API platform",
        "IDE tool",
    ],
    "data_platforms": [
        "data platform",
        "data infrastructure",
        "analytics",
        "data pipeline",
        "data warehouse",
    ],
    "robotics_ai": [
        "robotics",
        "robot AI",
        "autonomous robots",
        "embodied AI",
        "robot learning",
    ],
}


def _guess_lane_queries(lane: str) -> list[str]:
    """Return search queries for the given lane, falling back to a generic query."""
    queries = _LANE_QUERIES.get(lane)
    if queries:
        return queries
    readable = lane.replace("_", " ")
    return [readable, f"{readable} platform", f"{readable} tool"]


def search_github_orgs(lane: str, limit: int = 5) -> list[dict[str, Any]]:
    """Search GitHub for organisations active in a technical lane.

    Queries GitHub's repository search for repos matching lane keywords,
    then collects the owning organisation (or user) for each matching repo.

    Returns a list of dicts with:
        name (str)         — organisation / user login (GitHub handle)
        display_name (str) — human-readable name from the org profile, or login
        description (str)  — org description
        blog (str)         — org website URL
        repo_url (str)     — example matching repo URL
        source (str)       — ``"github_org"``
        lane (str)         — the lane that matched
        topic_hits (int)   — number of repos from this org that matched across queries

    Returns an empty list on any API failure or rate limit.
    """
    if lane in _ORG_CACHE:
        return _ORG_CACHE[lane][:limit]

    results: dict[str, dict[str, Any]] = {}
    queries = _guess_lane_queries(lane)

    def _safe_get(client: httpx.Client, url: str, headers: dict[str, str]) -> Any:
        """Fetch an org profile, returning the response or the raised exception.

        The exception is captured (not raised in the worker) so the sequential
        replay below can re-raise it at the exact point the original code would
        have — preserving the original "abort on a fetch error" behaviour.
        """
        try:
            return client.get(url, headers=headers)
        except Exception as exc:
            return exc

    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            headers = _auth_headers()

            seen_orgs: set[str] = set()
            for query in queries[:3]:
                resp = client.get(
                    f"{_GITHUB_API}/search/repositories",
                    params={
                        "q": query,
                        "sort": "stars",
                        "per_page": "10",
                        "type": "public",
                    },
                    headers=headers,
                )
                if resp.status_code != 200:
                    logger.debug("GitHub search failed for query '%s': %d", query, resp.status_code)
                    continue

                data = resp.json()
                items = data.get("items", [])

                # Determine the unique, not-yet-seen orgs in this query (in item
                # order) whose profile must be fetched, then fetch those profiles
                # concurrently. Bookkeeping (seen_orgs/results/topic_hits) is
                # replayed sequentially afterwards so semantics are unchanged.
                to_fetch: list[tuple[str, str]] = []
                planned: set[str] = set()
                for item in items:
                    owner = item.get("owner") or {}
                    owner_id = owner.get("login", "")
                    if not owner_id or owner.get("type") != "Organization":
                        continue
                    if owner_id in seen_orgs or owner_id in planned:
                        continue
                    planned.add(owner_id)
                    profile_url = owner.get("url") or f"{_GITHUB_API}/orgs/{owner_id}"
                    to_fetch.append((owner_id, profile_url))

                profiles: dict[str, Any] = {}
                if to_fetch:
                    with ThreadPoolExecutor(
                        max_workers=min(_MAX_PROFILE_WORKERS, len(to_fetch))
                    ) as pool:
                        fetched = pool.map(
                            lambda pair: _safe_get(client, pair[1], headers), to_fetch
                        )
                        for (owner_id, _url), res in zip(to_fetch, fetched):
                            profiles[owner_id] = res

                for item in items:
                    owner = item.get("owner") or {}
                    owner_id = owner.get("login", "")
                    if not owner_id or owner.get("type") != "Organization":
                        continue
                    if owner_id in seen_orgs:
                        key = owner_id.lower()
                        if key in results:
                            results[key]["topic_hits"] += 1
                        continue
                    seen_orgs.add(owner_id)

                    profile_resp = profiles.get(owner_id)
                    if isinstance(profile_resp, Exception):
                        raise profile_resp
                    if profile_resp is None or profile_resp.status_code != 200:
                        continue
                    profile = profile_resp.json()
                    if profile.get("type") not in {None, "Organization"}:
                        continue

                    blog = profile.get("blog", "") or ""
                    website = blog if blog.startswith("http") else f"https://{blog}" if blog else ""
                    if not website:
                        continue

                    results[owner_id.lower()] = {
                        "name": owner_id,
                        "display_name": profile.get("name") or owner_id,
                        "description": (
                            profile.get("description")
                            or profile.get("bio")
                            or item.get("description")
                            or ""
                        )[:200],
                        "website": website,
                        "repo_url": item.get("html_url", ""),
                        "repo_description": (item.get("description") or "")[:300],
                        "source": "github_org",
                        "lane": lane,
                        "topic_hits": 1,
                    }

                if len(results) >= limit * 2:
                    break

    except Exception as exc:
        logger.debug("GitHub org search failed for lane '%s': %s", lane, exc)

    ordered = sorted(results.values(), key=lambda r: r["topic_hits"], reverse=True)
    _ORG_CACHE[lane] = ordered
    return ordered[:limit]
