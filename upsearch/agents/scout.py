"""
Scout Agent — decides which sources and subreddits to search, then fetches posts.
Uses tool use so Claude actively chooses what to search rather than searching everything blindly.
"""
import json
import os
import anthropic
from upsearch.sourcing import reddit, hackernews
from upsearch.sourcing.base import Post

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

SYSTEM = """You are a Scout Agent in a cold outreach research pipeline.

Given a topic a student wants to explore, decide which sources to search and what refined queries will surface real open problems that engineers or researchers are actively struggling with.

You have two tools: search_reddit and search_hackernews. Call them with targeted queries. Prefer specificity over breadth. Focus on posts where someone is describing a hard problem, not asking basic questions or sharing news links."""

TOOLS = [
    {
        "name": "search_reddit",
        "description": "Search Reddit for posts about a topic. Returns posts from technical subreddits.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "subreddits": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of subreddit names to search. Pick from: MachineLearning, LocalLLaMA, mlops, compsci, programming, devops, artificial, datascience",
                },
            },
            "required": ["query", "subreddits"],
        },
    },
    {
        "name": "search_hackernews",
        "description": "Search Hacker News for stories about a topic.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
    },
]


def _run_tool(name: str, inputs: dict) -> list[Post]:
    if name == "search_reddit":
        return reddit.search(inputs["query"], subreddits=inputs.get("subreddits"), limit=6)
    if name == "search_hackernews":
        return hackernews.search(inputs["query"], limit=6)
    return []


def run(topic: str) -> list[Post]:
    messages = [{"role": "user", "content": f"Topic to research: {topic}\n\nSearch for posts where engineers or researchers describe real problems they're stuck on related to this topic."}]

    all_posts: list[Post] = []
    seen_urls: set[str] = set()

    while True:
        response = client.messages.create(
            model="claude-opus-4-8",
            max_tokens=1024,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
        )

        tool_calls = [b for b in response.content if b.type == "tool_use"]

        if not tool_calls:
            break

        tool_results = []
        for tc in tool_calls:
            posts = _run_tool(tc.name, tc.input)
            for p in posts:
                if p.url not in seen_urls:
                    seen_urls.add(p.url)
                    all_posts.append(p)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": f"Returned {len(posts)} posts.",
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            break

    return all_posts
