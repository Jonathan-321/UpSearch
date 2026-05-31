from dataclasses import dataclass, field


@dataclass
class Post:
    title: str
    body: str
    url: str
    source: str
    author: str = ""
    subreddit: str = ""
    score: int = 0
    comments: int = 0

    def to_text(self) -> str:
        lines = [f"Title: {self.title}", f"Source: {self.source}"]
        if self.subreddit:
            lines.append(f"Subreddit: r/{self.subreddit}")
        if self.author:
            lines.append(f"Author: {self.author}")
        if self.body.strip():
            lines.append(f"\n{self.body[:1200]}")
        lines.append(f"\nURL: {self.url}")
        return "\n".join(lines)
