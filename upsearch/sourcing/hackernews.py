import requests
from .base import Post

ALGOLIA = "https://hn.algolia.com/api/v1/search"


def search(query: str, limit: int = 5) -> list[Post]:
    posts = []

    # General story search
    try:
        r = requests.get(
            ALGOLIA,
            params={"query": query, "tags": "story", "hitsPerPage": limit},
            timeout=10,
        )
        r.raise_for_status()
        for hit in r.json().get("hits", []):
            body = hit.get("story_text") or ""
            posts.append(Post(
                title=hit.get("title", ""),
                body=body[:1200],
                url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                source="hackernews",
                author=hit.get("author", ""),
                score=hit.get("points", 0),
                comments=hit.get("num_comments", 0),
            ))
    except Exception:
        pass

    # Also search Ask HN / Who's Hiring threads for job-related queries
    job_keywords = {"job", "hiring", "intern", "internship", "role", "engineer", "position"}
    if any(kw in query.lower() for kw in job_keywords):
        try:
            r = requests.get(
                ALGOLIA,
                params={"query": query, "tags": "ask_hn", "hitsPerPage": limit},
                timeout=10,
            )
            r.raise_for_status()
            for hit in r.json().get("hits", []):
                body = hit.get("story_text") or ""
                if not body.strip():
                    continue
                posts.append(Post(
                    title=hit.get("title", ""),
                    body=body[:1200],
                    url=f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                    source="hackernews",
                    author=hit.get("author", ""),
                    score=hit.get("points", 0),
                    comments=hit.get("num_comments", 0),
                ))
        except Exception:
            pass

    return posts
