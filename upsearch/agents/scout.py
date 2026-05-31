"""
Scout Agent — decides which sources and subreddits to search, then fetches posts.
Uses tool use so the model actively chooses what to search.
Works with both Claude (Anthropic tool-use) and DeepSeek (OpenAI-compatible function calling).
"""
import json
from upsearch.sourcing import reddit, hackernews
from upsearch.sourcing.base import Post
from upsearch import llm

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
                    "description": "Subreddit names to search. Pick from: MachineLearning, LocalLLaMA, mlops, compsci, programming, devops, artificial, datascience",
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


def _execute_tool(name: str, inputs: dict) -> list[Post]:
    if name == "search_reddit":
        return reddit.search(inputs["query"], subreddits=inputs.get("subreddits"), limit=6)
    if name == "search_hackernews":
        return hackernews.search(inputs["query"], limit=6)
    return []


def _run_claude(topic: str) -> list[Post]:
    """Claude variant — uses Anthropic multi-turn tool-use loop."""
    import anthropic
    import os

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    messages = [{"role": "user", "content": f"Topic: {topic}\n\nSearch for posts where engineers or researchers describe real problems they are stuck on related to this topic."}]
    all_posts: list[Post] = []
    seen: set[str] = set()

    while True:
        response = client.messages.create(
            model=llm.CLAUDE_MODEL,
            max_tokens=1024,
            system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            tools=TOOLS,
            messages=messages,
        )

        tool_blocks = [b for b in response.content if b.type == "tool_use"]
        if not tool_blocks:
            break

        tool_results = []
        for tc in tool_blocks:
            posts = _execute_tool(tc.name, tc.input)
            for p in posts:
                if p.url not in seen:
                    seen.add(p.url)
                    all_posts.append(p)
            tool_results.append({"type": "tool_result", "tool_use_id": tc.id, "content": f"Returned {len(posts)} posts."})

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

        if response.stop_reason == "end_turn":
            break

    return all_posts


def _run_deepseek(topic: str) -> list[Post]:
    """DeepSeek variant — uses OpenAI-compatible function calling loop."""
    from openai import OpenAI
    import os

    client = OpenAI(
        api_key=os.environ.get("DEEPSEEK_API_KEY"),
        base_url="https://api.deepseek.com/v1",
    )

    oai_tools = [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in TOOLS
    ]

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Topic: {topic}\n\nSearch for posts where engineers or researchers describe real problems they are stuck on related to this topic."},
    ]

    all_posts: list[Post] = []
    seen: set[str] = set()

    for _ in range(4):  # max 4 rounds
        response = client.chat.completions.create(
            model=llm.DEEPSEEK_MODEL,
            max_tokens=1024,
            messages=messages,
            tools=oai_tools,
            tool_choice="auto",
        )
        choice = response.choices[0]

        if not choice.message.tool_calls:
            break

        # Add assistant message
        messages.append({
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in choice.message.tool_calls
            ],
        })

        # Execute tools and add results
        for tc in choice.message.tool_calls:
            inputs = json.loads(tc.function.arguments)
            posts = _execute_tool(tc.function.name, inputs)
            for p in posts:
                if p.url not in seen:
                    seen.add(p.url)
                    all_posts.append(p)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": f"Returned {len(posts)} posts.",
            })

        if choice.finish_reason == "stop":
            break

    return all_posts


def run(topic: str) -> list[Post]:
    if llm.PROVIDER == "deepseek":
        return _run_deepseek(topic)
    return _run_claude(topic)
