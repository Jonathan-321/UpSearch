import time
from concurrent.futures import ThreadPoolExecutor

import requests

from .base import Post

ALGOLIA = "https://hn.algolia.com/api/v1/search"

# Discovery wants recent signals, not 2017-era launches. Posts older than
# this default are excluded via Algolia's numericFilters on created_at_i.
# Callers can pass a different bound, or max_age_days=None to disable it.
DEFAULT_MAX_AGE_DAYS = 540


def _freshness_filter(max_age_days: int | None) -> str | None:
    """Build an Algolia numericFilters clause bounding post age, or None."""
    if max_age_days is None or max_age_days <= 0:
        return None
    cutoff = int(time.time()) - max_age_days * 86400
    return f"created_at_i>{cutoff}"


def search(
    query: str,
    limit: int = 5,
    max_age_days: int | None = DEFAULT_MAX_AGE_DAYS,
) -> list[Post]:
    posts = []
    freshness = _freshness_filter(max_age_days)

    # Build the request plan: the general story search always runs; the Ask HN
    # search only runs for job-related queries. Both are independent Algolia
    # requests, so they are fetched concurrently and processed in plan order.
    specs: list[tuple[str, dict[str, str | int]]] = []

    story_params: dict[str, str | int] = {"query": query, "tags": "story", "hitsPerPage": limit}
    if freshness:
        story_params["numericFilters"] = freshness
    specs.append(("story", story_params))

    job_keywords = {"job", "hiring", "intern", "internship", "role", "engineer", "position"}
    if any(kw in query.lower() for kw in job_keywords):
        ask_params: dict[str, str | int] = {"query": query, "tags": "ask_hn", "hitsPerPage": limit}
        if freshness:
            ask_params["numericFilters"] = freshness
        specs.append(("ask_hn", ask_params))

    def _fetch(params: dict[str, str | int]):
        """Run one Algolia request; return the response or None on any failure."""
        try:
            r = requests.get(ALGOLIA, params=params, timeout=10)
            r.raise_for_status()
            return r
        except Exception:
            return None

    if len(specs) == 1:
        responses = [_fetch(specs[0][1])]
    else:
        with ThreadPoolExecutor(max_workers=len(specs)) as pool:
            responses = list(pool.map(lambda spec: _fetch(spec[1]), specs))

    for (tag, _params), r in zip(specs, responses):
        if r is None:
            continue
        try:
            hits = r.json().get("hits", [])
        except Exception:
            continue
        for hit in hits:
            body = hit.get("story_text") or ""
            if tag == "ask_hn":
                if not body.strip():
                    continue
                url = f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            else:
                url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            posts.append(Post(
                title=hit.get("title", ""),
                body=body[:1200],
                url=url,
                source="hackernews",
                author=hit.get("author", ""),
                score=hit.get("points", 0),
                comments=hit.get("num_comments", 0),
            ))

    return posts
