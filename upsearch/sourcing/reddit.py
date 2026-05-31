import requests
from .base import Post

HEADERS = {"User-Agent": "UpSearch/1.0 research-outreach-tool"}

DEFAULT_SUBREDDITS = [
    "MachineLearning",
    "LocalLLaMA",
    "mlops",
    "compsci",
    "programming",
    "devops",
]


def search(query: str, subreddits: list[str] | None = None, limit: int = 5) -> list[Post]:
    targets = subreddits or DEFAULT_SUBREDDITS
    posts = []

    for sub in targets:
        try:
            r = requests.get(
                f"https://www.reddit.com/r/{sub}/search.json",
                headers=HEADERS,
                params={"q": query, "limit": limit, "sort": "relevance", "t": "year"},
                timeout=10,
            )
            r.raise_for_status()
            for item in r.json()["data"]["children"]:
                d = item["data"]
                if d.get("is_self") is False and not d.get("selftext"):
                    continue
                posts.append(Post(
                    title=d.get("title", ""),
                    body=(d.get("selftext") or "")[:1200],
                    url=f"https://reddit.com{d.get('permalink', '')}",
                    source="reddit",
                    author=d.get("author", ""),
                    subreddit=sub,
                    score=d.get("score", 0),
                    comments=d.get("num_comments", 0),
                ))
        except Exception:
            continue

    return posts
