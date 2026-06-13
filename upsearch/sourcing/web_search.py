"""Simple web search for company research — uses DuckDuckGo (free, no API key).

Used by the Problem agent to find engineering blogs, company posts, and
technical discussions that Google/DuckDuckGo surfaces but HN/Reddit misses.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(8.0, connect=4.0)
_HEADERS = {
    "User-Agent": "UpSearchWebSearch/0.1 (research; muhirejonathan123@gmail.com)",
    "Accept": "text/html,application/xhtml+xml",
}

# DuckDuckGo HTML search — no API key needed
DDG_URL = "https://html.duckduckgo.com/html/"


def search(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Search the web via DuckDuckGo. Free, no API key.

    Returns list of {title, url, snippet}.
    Returns empty list on failure.
    """
    results: list[dict[str, str]] = []
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.post(
                DDG_URL,
                data={"q": query},
                headers=_HEADERS,
            )
            if resp.status_code != 200:
                return results

            # Parse result links from the HTML
            for match in re.finditer(
                r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>([^<]+)</a>',
                resp.text,
            ):
                url = match.group(1)
                title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
                if url and title and len(results) < limit:
                    from html import unescape  # noqa: PLC0415
                    results.append({"title": unescape(title), "url": url})
    except Exception as exc:
        logger.debug("Web search failed for '%s': %s", query, exc)

    return results


def search_company_blog(company_name: str, domain: str = "") -> list[dict[str, str]]:
    """Search for engineering blog posts from a specific company.

    Uses site-specific search if domain is available.
    """
    if domain:
        query = f"site:{domain} engineering blog post 2026"
    else:
        query = f"{company_name} engineering blog 2026"
    return search(query, limit=5)


def search_company_problems(company_name: str, lane: str) -> list[dict[str, str]]:
    """Search for technical problems/challenges a company is facing."""
    queries = [
        f"{company_name} {lane} engineering challenge 2026",
        f"{company_name} technical blog 2026",
        f"{company_name} engineering team building 2026",
        f"{company_name} open source 2026",
    ]
    # Each query is an independent DuckDuckGo request with no shared state, and
    # every query always runs (results are capped only at the end). Fetch them
    # concurrently, then merge in query order so dedup/order stays identical.
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        per_query = list(pool.map(lambda q: search(q, limit=3), queries))

    results: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    for query_results in per_query:
        for r in query_results:
            if r["url"] not in seen_urls:
                seen_urls.add(r["url"])
                results.append(r)
    return results[:8]
