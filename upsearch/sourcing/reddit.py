import requests
from .base import Post

HEADERS = {"User-Agent": "UpSearch/1.0 research-outreach-tool"}

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

    for sub in subreddits:
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
