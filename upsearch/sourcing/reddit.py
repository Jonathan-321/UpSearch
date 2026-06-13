import logging
from concurrent.futures import ThreadPoolExecutor

import requests

from .base import Post

logger = logging.getLogger(__name__)

# Reddit returns HTTP 403 to unauthenticated requests with script-style
# user agents. A browser-style UA plus the old.reddit.com host is the most
# reliable unauthenticated path to search.json.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
}

SEARCH_HOST = "https://old.reddit.com"

# Statuses meaning "Reddit refused us", not "our request was malformed".
_BLOCKED_STATUSES = {401, 403, 429}

# When Reddit blocks us we return explicit-empty (no fabrication), but say
# so once per process run at info level instead of silently swallowing it.
_blocked_logged = False


def _log_blocked_once(status_code: int) -> None:
    global _blocked_logged
    if not _blocked_logged:
        logger.info(
            "Reddit search blocked (HTTP %s); returning no Reddit results this run.",
            status_code,
        )
        _blocked_logged = True


RESEARCH_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "mlops",
    "compsci",
    "programming",
    "artificial",
]

JOB_SUBREDDITS = [
    "cscareerquestions",
    "MachineLearning",
    "mlops",
    "LocalLLaMA",
    "cscareerquestions",
    "datascience",
]


def search(query: str, subreddits: list[str] | None = None, limit: int = 5) -> list[Post]:
    # Auto-pick subreddits based on query content if not specified
    if subreddits is None:
        job_keywords = {"job", "hiring", "intern", "internship", "role", "position", "career"}
        is_job = any(kw in query.lower() for kw in job_keywords)
        subreddits = JOB_SUBREDDITS if is_job else RESEARCH_SUBREDDITS

    posts = []
    seen = set()

    def _fetch(sub: str):
        """Run one subreddit search; return the response or the raised error."""
        try:
            return requests.get(
                f"{SEARCH_HOST}/r/{sub}/search.json",
                headers=HEADERS,
                params={"q": query, "limit": limit, "sort": "relevance", "t": "year"},
                timeout=10,
            )
        except Exception as exc:
            return exc

    # The per-subreddit searches are independent blocking requests. Fetch them
    # concurrently, then process responses in the original subreddit order so
    # dedup, "blocked once" logging, and result ordering are unchanged.
    with ThreadPoolExecutor(max_workers=min(8, len(subreddits) or 1)) as pool:
        responses = list(pool.map(_fetch, subreddits))

    for sub, r in zip(subreddits, responses):
        try:
            if isinstance(r, Exception):
                raise r
            if r.status_code in _BLOCKED_STATUSES:
                _log_blocked_once(r.status_code)
                continue
            r.raise_for_status()
            for item in r.json()["data"]["children"]:
                d = item["data"]
                url = f"https://reddit.com{d.get('permalink', '')}"
                if url in seen:
                    continue
                seen.add(url)
                posts.append(Post(
                    title=d.get("title", ""),
                    body=(d.get("selftext") or "")[:1200],
                    url=url,
                    source="reddit",
                    author=d.get("author", ""),
                    subreddit=sub,
                    score=d.get("score", 0),
                    comments=d.get("num_comments", 0),
                ))
        except Exception:
            continue

    return posts
