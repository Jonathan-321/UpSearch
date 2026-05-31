"""
Strategist Agent — given the analysis, decides exactly who to contact,
what the outreach angle is, and which channel to use first.
"""
import json
from upsearch.sourcing.base import Post
from upsearch import llm

SYSTEM = """You are a Strategist Agent in a cold outreach research pipeline.

Given a technical analysis and a student profile, decide:
1. Who specifically to target (role, not a name)
2. The one-line outreach hook — why THEM, why NOW, why THIS student
3. Which channel to use first
4. One specific piece of context from the post to use as an icebreaker

Respond with valid JSON only, no markdown fences:
{
  "target_role": "e.g. 'ML engineer on the inference team' or 'PhD researcher in LLM serving'",
  "hook": "one sentence — the core reason they should reply",
  "channel": "email" | "linkedin",
  "icebreaker": "one specific detail from their post/work to open with"
}"""


def run(post: Post, analysis: dict, user_profile: str) -> dict | None:
    payload = (
        f"Post title: {post.title}\n"
        f"Source: {post.source} — {post.url}\n\n"
        f"Analysis:\n{json.dumps(analysis, indent=2)}\n\n"
        f"Student profile:\n{user_profile}"
    )
    text = llm.complete(system=SYSTEM, user=payload, max_tokens=384)
    start, end = text.find("{"), text.rfind("}") + 1
    if start == -1 or end == 0:
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return None
