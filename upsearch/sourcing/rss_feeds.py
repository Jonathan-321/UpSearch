"""RSS feed connector for tech news and startup coverage.

Fetches from free RSS feeds (no API key required):
- TechCrunch: startup news, funding announcements
- Y Combinator blog: new batch companies
- Hacker News front page: trending tech discussions
"""

from __future__ import annotations

import re
from typing import Any
from xml.etree import ElementTree

import httpx


_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_HEADERS = {
    "User-Agent": "UpSearchRssConnector/0.1",
    "Accept": "application/rss+xml, application/xml, text/xml, */*;q=0.8",
}

FEEDS: dict[str, str] = {
    "techcrunch": "https://techcrunch.com/feed/",
    "techcrunch_startups": "https://techcrunch.com/category/startups/feed/",
    "techcrunch_funding": "https://techcrunch.com/category/funding/feed/",
    "yc_blog": "https://blog.ycombinator.com/feed/",
    "venturebeat": "https://venturebeat.com/feed/",
    "thenewstack": "https://thenewstack.io/feed/",
}


def _parse_item(item: ElementTree.Element, source: str) -> dict[str, Any] | None:
    """Extract title, link, summary from an RSS item."""
    title_el = item.find("title")
    link_el = item.find("link")
    desc_el = item.find("description")
    title = title_el.text.strip() if title_el is not None and title_el.text else ""
    link = link_el.text.strip() if link_el is not None and link_el.text else ""
    summary = ""
    if desc_el is not None and desc_el.text:
        summary = re.sub(r"<[^>]+>", " ", desc_el.text).strip()[:500]

    if not title:
        return None
    return {
        "title": title,
        "link": link,
        "summary": summary,
        "source": source,
    }


def _extract_company_name(title: str) -> str | None:
    """Try to extract a company name from a tech news title.

    Patterns:
    - "CompanyName raises $X Series Y" → CompanyName
    - "CompanyName launches ..." → CompanyName
    - "CompanyName acquires ..." → CompanyName
    """
    # Series A/B/C funding
    for match in re.finditer(r"^([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\s+(?:raises|nabs|gets|wins|lands|secures)", title):
        return match.group(1).strip()
    # "CompanyName launches/announces/introduces"
    for match in re.finditer(r"^([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\s+(?:launches|announces|introduces|debuts|unveils|partners|acquires)", title):
        return match.group(1).strip()
    # "YC-backed CompanyName raises"
    for match in re.finditer(r"YC[- ]backed\s+([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)", title):
        return match.group(1).strip()
    # "CompanyName, the X-backed startup, raises" — comma after name
    for match in re.finditer(r"^([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*),\s+(?:the|a|an)\s+", title):
        return match.group(1).strip()
    # "CompanyName (pronounced ...) raises" or "CompanyName nabs"
    for match in re.finditer(r"^([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)*)\s+(?:doubles|raises|nabs|gets|wins|lands|secures|closes|picks up)", title):
        return match.group(1).strip()
    return None


def search(feed_names: list[str] | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Fetch RSS feeds and return items with extracted company names.

    Args:
        feed_names: List of feed keys to fetch (defaults to all).
        limit: Max items to return.

    Returns:
        List of dicts with title, link, summary, source, company_name.
    """
    if feed_names is None:
        feed_names = list(FEEDS.keys())

    results: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for name in feed_names:
        url = FEEDS.get(name)
        if not url:
            continue
        try:
            with httpx.Client(timeout=_TIMEOUT, follow_redirects=True) as client:
                resp = client.get(url, headers=_HEADERS)
                resp.raise_for_status()
                root = ElementTree.fromstring(resp.content)
                # RSS feeds have channel → item
                channel = root.find("channel")
                items = channel.findall("item") if channel is not None else root.findall("item")
                for item in items:
                    parsed = _parse_item(item, name)
                    if not parsed:
                        continue
                    if parsed["link"] in seen_links:
                        continue
                    seen_links.add(parsed["link"])
                    company = _extract_company_name(parsed["title"])
                    if company:
                        parsed["company_name"] = company
                    results.append(parsed)
                    if len(results) >= limit:
                        return results
        except Exception:
            continue

    return results
